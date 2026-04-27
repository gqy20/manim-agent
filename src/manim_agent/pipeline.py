"""Pipeline 编排：Claude Agent SDK → TTS → FFmpeg 的完整执行流程。

包含 run_pipeline() 及其全部辅助函数（options 构建、prompt 包装、
解说生成、render review、PO 元数据填充等）。
"""

import asyncio  # noqa: F401 - compatibility patch surface for tests/callers.
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from claude_agent_sdk import query

from . import music_client, prompts, render_review, tts_client, video_builder  # noqa: F401
from . import pipeline_narration as _pipeline_narration_module
from . import pipeline_phases12 as _pipeline_phases12_module
from . import pipeline_phases345 as _pipeline_phases345_module
from .dispatcher import _EMOJI, _LOG_SEPARATOR, _MessageDispatcher
from .hooks import activate_hook_state, create_hook_state, reset_hook_state
from .phase2_script_analyzer import analyze_phase2_script, persist_phase2_script_analysis
from .pipeline_config import (
    build_options as _build_options,
)
from .pipeline_config import (
    emit_phase_enter as _emit_phase_enter,
)
from .pipeline_config import (
    emit_phase_exit as _emit_phase_exit,
)
from .pipeline_config import (
    emit_status as _emit_status,
)
from .pipeline_config import (
    stderr_handler as _stderr_handler,
)
from .pipeline_gates import (
    apply_phase2_build_spec_defaults,
    implementation_contract_issue,
    merge_result_summaries,
)
from .pipeline_narration import generate_narration
from .pipeline_phases12 import (
    build_implementation_prompt,
    build_phase2_script_draft_prompt,
    build_phase2_script_repair_prompt,
    build_scene_plan_prompt,
    reset_phase2_script_draft_capture,
    run_phase1_planning,
    run_phase2_implementation,
    run_phase2_script_draft,
)
from .pipeline_phases345 import (
    run_phase3_render,
    run_phase4_tts,
    run_phase5_mux,
    run_render_review,
)
from .pipeline_trace import TraceSpan, create_trace_id
from .prompt_debug import update_prompt_artifact, write_prompt_artifact
from .schemas import PhaseSchemaRegistry

logger = logging.getLogger(__name__)

# ── Test patch hooks ─────────────────


stderr_handler = _stderr_handler
_run_render_review = run_render_review


def _debug_dump(value: Any) -> Any:
    """Return a debug snapshot without assuming the value is a Pydantic model."""
    if value is None:
        return None
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump()
    return value


# ── Main Pipeline ────────────────────────────────────────────────────


async def run_pipeline(
    user_text: str,
    output_path: str,
    voice_id: str = "female-tianmei",
    model: str = "speech-2.8-hd",
    quality: str = "high",
    no_tts: bool = False,
    no_render_review: bool = True,
    bgm_enabled: bool = False,
    bgm_prompt: str | None = None,
    bgm_volume: float = 0.12,
    target_duration_seconds: int = 60,
    cwd: str = ".",
    prompt_file: str | None = None,
    max_turns: int = 50,
    log_callback: Callable[[str], None] | None = None,
    preset: str = "default",
    render_mode: str = "full",
    intro_outro: bool = False,
    intro_outro_backend: str = "revideo",
    _dispatcher_ref: list[Any] | None = None,
    event_callback: Callable[[Any], None] | None = None,
) -> str:
    """Run the full Claude -> TTS -> mux pipeline."""
    resolved_cwd = str(Path(cwd).resolve())
    bgm_volume = min(max(bgm_volume, 0.0), 1.0)
    render_mode = render_mode.strip().lower() or "full"
    planning_system_prompt = prompts.get_planning_prompt(
        preset=preset,
        quality=quality,
        render_mode=render_mode,
    )
    implementation_system_prompt = prompts.get_implementation_prompt(
        preset=preset,
        quality=quality,
        cwd=resolved_cwd,
    )
    script_draft_system_prompt = prompts.get_phase2_script_draft_prompt(
        preset=preset,
        quality=quality,
        cwd=resolved_cwd,
    )
    render_review_system_prompt = prompts.get_render_review_prompt(
        preset=preset,
        quality=quality,
        cwd=resolved_cwd,
    )
    narration_system_prompt = prompts.get_narration_prompt(
        preset=preset,
        quality=quality,
        cwd=resolved_cwd,
    )

    planning_options = _build_options(
        cwd=resolved_cwd,
        system_prompt=planning_system_prompt,
        max_turns=min(max_turns, 16),
        prompt_file=prompt_file,
        quality=quality,
        log_callback=log_callback,
        output_format=PhaseSchemaRegistry.output_format_schema("phase1_planning"),
        use_default_output_format=False,
        tools=[],
        allowed_tools=[],
        disallowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        skills=[],
    )
    build_opts = _build_options(
        cwd=resolved_cwd,
        system_prompt=implementation_system_prompt,
        max_turns=max_turns,
        prompt_file=prompt_file,
        quality=quality,
        log_callback=log_callback,
        output_format=PhaseSchemaRegistry.output_format_schema("phase2_implementation"),
        use_default_output_format=False,
    )
    script_draft_opts = _build_options(
        cwd=resolved_cwd,
        system_prompt=script_draft_system_prompt,
        max_turns=max_turns,
        prompt_file=prompt_file,
        quality=quality,
        log_callback=log_callback,
        output_format=PhaseSchemaRegistry.output_format_schema("phase2_script_draft"),
        use_default_output_format=False,
        allowed_tools=["Read", "Write", "Edit", "Glob", "Grep"],
        disallowed_tools=["Bash"],
    )

    hook_state = create_hook_state(event_callback=event_callback)
    hook_state_token = activate_hook_state(hook_state)
    dispatcher = _MessageDispatcher(
        verbose=True,
        log_callback=log_callback,
        output_cwd=resolved_cwd,
        hook_state=hook_state,
        expected_output="phase1_planning",
    )
    if _dispatcher_ref is not None:
        _dispatcher_ref.append(dispatcher)
    if event_callback is not None:
        dispatcher.event_callback = event_callback

    # ── 接入 Trace/Span 全链路追踪 ──
    pipeline_trace_id = create_trace_id()
    TraceSpan._emit_event_fn = event_callback  # 让 span enter/exit 自动发射到 SSE

    dispatcher._print(f"\n{_LOG_SEPARATOR}")
    dispatcher._print(
        f"  Claude Agent Log                              Session: {build_opts.session_id[:8]}..."
    )
    dispatcher._print(_LOG_SEPARATOR)
    dispatcher._print(f"  {_EMOJI['gear']} Phase 1/5: scene planning pass")
    dispatcher._print(
        f"  quality={quality} preset={preset} max_turns={max_turns} "
        f"target_duration={target_duration_seconds}s"
    )
    if build_opts.plugins:
        plugin_labels = ", ".join(
            Path(plugin["path"]).name for plugin in build_opts.plugins if plugin.get("path")
        )
        dispatcher._print(f"  [SYS] Plugins loaded: {plugin_labels}")
    if planning_options.allowed_tools:
        dispatcher._print(f"  [SYS] Allowed tools: {', '.join(planning_options.allowed_tools)}")
    _emit_status(
        event_callback,
        task_status="running",
        phase="init",
        message="Claude Agent SDK started",
    )

    _cli_stderr_lines: list[str] = []
    _orig_log_callback = log_callback

    def _counting_log_callback(line: str) -> None:
        _cli_stderr_lines.append(line)
        if _orig_log_callback:
            _orig_log_callback(line)

    planning_options.stderr = lambda line: _counting_log_callback(line)
    script_draft_opts.stderr = lambda line: _counting_log_callback(line)
    build_opts.stderr = lambda line: _counting_log_callback(line)

    try:
        _pipeline_phases12_module.query = query
        _pipeline_narration_module.query = query
        _pipeline_phases345_module.run_render_review = _run_render_review
        _pipeline_phases345_module.extract_review_frames = render_review.extract_review_frames
        _pipeline_phases345_module.build_final_video = video_builder.build_final_video
        _pipeline_phases345_module.concat_videos = video_builder.concat_videos
        _pipeline_phases345_module._get_duration = video_builder._get_duration
        # ══════════════════════════════════════════════
        # Phase 1/5: Scene Planning Pass
        # ══════════════════════════════════════════════
        _emit_phase_enter(
            event_callback,
            phase_id="phase1",
            phase_name="Scene Planning",
            trace_id=pipeline_trace_id,
        )
        planning_result_summary: dict[str, Any] | None = None
        hook_state.allowed_tools = (
            set(planning_options.allowed_tools)
            if planning_options.allowed_tools is not None
            else None
        )
        planning_prompt = build_scene_plan_prompt(
            user_text,
            target_duration_seconds,
            preset=preset,
            quality=quality,
            render_mode=render_mode,
        )
        common_debug_inputs = {
            "user_text": user_text,
            "target_duration_seconds": target_duration_seconds,
            "quality": quality,
            "preset": preset,
            "render_mode": render_mode,
            "voice_id": voice_id,
            "model": model,
            "no_tts": no_tts,
            "bgm_enabled": bgm_enabled,
        }
        write_prompt_artifact(
            output_dir=resolved_cwd,
            phase_id="phase1",
            phase_name="Scene Planning",
            system_prompt=planning_system_prompt,
            user_prompt=planning_prompt,
            inputs=common_debug_inputs,
            options=planning_options,
            options_summary={"output_schema": "phase1_planning"},
        )
        planning_result_summary = await run_phase1_planning(
            planning_prompt=planning_prompt,
            target_duration_seconds=target_duration_seconds,
            planning_options=planning_options,
            system_prompt=planning_system_prompt,
            quality=quality,
            prompt_file=prompt_file,
            log_callback=log_callback,
            resolved_cwd=resolved_cwd,
            dispatcher=dispatcher,
            event_callback=event_callback,
        )

        plan_text = dispatcher.partial_plan_text
        build_spec = getattr(dispatcher, "partial_build_spec", None)
        update_prompt_artifact(
            output_dir=resolved_cwd,
            phase_id="phase1",
            output_snapshot={
                "plan_text": plan_text,
                "build_spec": _debug_dump(build_spec),
                "result_summary": planning_result_summary,
            },
        )
        _emit_phase_exit(
            event_callback,
            phase_id="phase1",
            phase_name="Scene Planning",
            trace_id=pipeline_trace_id,
            beats_count=len(build_spec.beats) if hasattr(build_spec, "beats") else None,
        )
        if build_spec is not None:
            _beats = getattr(build_spec, "beats", None) or []
            _emit_status(
                event_callback,
                task_status="running",
                phase="planning",
                message="Phase 1 planning complete. Build spec ready.",
                pipeline_output={
                    "plan_text": plan_text or "",
                    "target_duration_seconds": target_duration_seconds,
                    "mode": getattr(build_spec, "mode", None),
                    "learning_goal": getattr(build_spec, "learning_goal", None),
                    "audience": getattr(build_spec, "audience", None),
                    "beats": [
                        {
                            "id": getattr(b, "id", None),
                            "title": getattr(b, "title", ""),
                            "visual_goal": getattr(b, "visual_goal", ""),
                            "narration_intent": getattr(b, "narration_intent", ""),
                            "target_duration_seconds": getattr(b, "target_duration_seconds", None),
                        }
                        for b in _beats
                    ],
                },
            )
        dispatcher.expected_output = "phase2_script_draft"
        dispatcher.partial_render_mode = render_mode
        dispatcher.partial_segment_render_complete = False
        dispatcher._print(f"  {_EMOJI['gear']} Phase 2A/5: beat-first script draft")
        _emit_status(
            event_callback,
            task_status="running",
            phase="scene",
            message="Phase 2A script draft started. Writing beat-first scene.py before rendering.",
        )
        _emit_phase_enter(
            event_callback,
            phase_id="phase2a",
            phase_name="Script Draft",
            trace_id=pipeline_trace_id,
        )
        if script_draft_opts.allowed_tools:
            dispatcher._print(
                f"  [SYS] Allowed tools: {', '.join(script_draft_opts.allowed_tools)}"
            )
        hook_state.allowed_tools = (
            set(script_draft_opts.allowed_tools)
            if script_draft_opts.allowed_tools is not None
            else None
        )

        # ══════════════════════════════════════════════
        # Phase 2/5: Implementation Pass
        # ══════════════════════════════════════════════
        script_draft_prompt = build_phase2_script_draft_prompt(
            user_text,
            target_duration_seconds,
            build_spec,
            resolved_cwd,
            render_mode=render_mode,
        )
        write_prompt_artifact(
            output_dir=resolved_cwd,
            phase_id="phase2a",
            phase_name="Script Draft",
            system_prompt=script_draft_system_prompt,
            user_prompt=script_draft_prompt,
            inputs={
                **common_debug_inputs,
                "build_spec": _debug_dump(build_spec),
            },
            options=script_draft_opts,
            options_summary={"output_schema": "phase2_script_draft"},
            referenced_artifacts={"phase1_planning": "phase1_planning.json"},
        )
        script_draft_result_summary = await run_phase2_script_draft(
            script_draft_prompt=script_draft_prompt,
            script_draft_options_instance=script_draft_opts,
            dispatcher=dispatcher,
            resolved_cwd=resolved_cwd,
        )
        draft_output = dispatcher.get_phase2_script_draft_output()
        draft_analysis = analyze_phase2_script(
            scene_file=getattr(draft_output, "scene_file", None),
            scene_class=getattr(draft_output, "scene_class", None),
            build_spec=build_spec,
            target_duration_seconds=target_duration_seconds,
            output_dir=resolved_cwd,
        )
        draft_analysis_path = persist_phase2_script_analysis(
            draft_analysis,
            output_dir=resolved_cwd,
            filename="phase2_script_draft_analysis.json",
        )
        dispatcher.phase2_script_draft_analysis_path = draft_analysis_path
        dispatcher._print(f"  [BUILD] Phase 2A script analysis persisted: {draft_analysis_path}")
        update_prompt_artifact(
            output_dir=resolved_cwd,
            phase_id="phase2a",
            output_snapshot={
                "draft_output": _debug_dump(draft_output),
                "draft_analysis": draft_analysis.model_dump(),
                "analysis_path": draft_analysis_path,
                "result_summary": script_draft_result_summary,
            },
        )
        if not draft_analysis.accepted:
            for issue in draft_analysis.issues:
                dispatcher._print(f"  [BUILD][ERR] {issue}")
            dispatcher._print("  [BUILD] Phase 2A repair pass started.")
            _emit_status(
                event_callback,
                task_status="running",
                phase="script_draft",
                message="Phase 2A script draft rejected. Starting focused repair pass.",
            )
            reset_phase2_script_draft_capture(dispatcher)
            repair_prompt = build_phase2_script_repair_prompt(
                user_text,
                target_duration_seconds,
                build_spec,
                draft_analysis.model_dump(),
                resolved_cwd,
                render_mode=render_mode,
            )
            write_prompt_artifact(
                output_dir=resolved_cwd,
                phase_id="phase2a-repair",
                phase_name="Script Draft Repair",
                system_prompt=script_draft_system_prompt,
                user_prompt=repair_prompt,
                inputs={
                    **common_debug_inputs,
                    "build_spec": _debug_dump(build_spec),
                    "failed_analysis": draft_analysis.model_dump(),
                },
                options=script_draft_opts,
                options_summary={"output_schema": "phase2_script_draft"},
                referenced_artifacts={
                    "phase1_planning": "phase1_planning.json",
                    "failed_analysis": "phase2_script_draft_analysis.json",
                },
            )
            repair_result_summary = await run_phase2_script_draft(
                script_draft_prompt=repair_prompt,
                script_draft_options_instance=script_draft_opts,
                dispatcher=dispatcher,
                resolved_cwd=resolved_cwd,
            )
            script_draft_result_summary = (
                merge_result_summaries(script_draft_result_summary, repair_result_summary)
                or script_draft_result_summary
            )
            draft_output = dispatcher.get_phase2_script_draft_output()
            draft_analysis = analyze_phase2_script(
                scene_file=getattr(draft_output, "scene_file", None),
                scene_class=getattr(draft_output, "scene_class", None),
                build_spec=build_spec,
                target_duration_seconds=target_duration_seconds,
                output_dir=resolved_cwd,
            )
            draft_analysis_path = persist_phase2_script_analysis(
                draft_analysis,
                output_dir=resolved_cwd,
                filename="phase2_script_draft_analysis.json",
            )
            dispatcher.phase2_script_draft_analysis_path = draft_analysis_path
            update_prompt_artifact(
                output_dir=resolved_cwd,
                phase_id="phase2a-repair",
                output_snapshot={
                    "draft_output": _debug_dump(draft_output),
                    "draft_analysis": draft_analysis.model_dump(),
                    "analysis_path": draft_analysis_path,
                    "result_summary": repair_result_summary,
                },
            )
            update_prompt_artifact(
                output_dir=resolved_cwd,
                phase_id="phase2a",
                output_snapshot={
                    "draft_output": _debug_dump(draft_output),
                    "draft_analysis": draft_analysis.model_dump(),
                    "analysis_path": draft_analysis_path,
                    "result_summary": script_draft_result_summary,
                    "repair_attempted": True,
                },
            )
            if not draft_analysis.accepted:
                for issue in draft_analysis.issues:
                    dispatcher._print(f"  [BUILD][ERR] {issue}")
                raise RuntimeError(
                    "Phase 2A script draft analysis failed after repair. Blocking issue: "
                    + "; ".join(draft_analysis.issues)
                )
            dispatcher._print("  [BUILD] Phase 2A repair accepted.")
        _emit_phase_exit(
            event_callback,
            phase_id="phase2a",
            phase_name="Script Draft",
            trace_id=pipeline_trace_id,
            beats_count=len(draft_analysis.expected_beat_ids),
            metadata={"analysis_path": draft_analysis_path},
        )
        if draft_output is not None:
            _emit_status(
                event_callback,
                task_status="running",
                phase="script_draft",
                message="Phase 2A script draft accepted.",
                pipeline_output={
                    "scene_file": getattr(draft_output, "scene_file", None),
                    "scene_class": getattr(draft_output, "scene_class", None),
                    "implemented_beats": list(getattr(draft_output, "implemented_beats", []) or []),
                    "build_summary": getattr(draft_output, "build_summary", None) or "",
                    "estimated_duration_seconds": getattr(
                        draft_output,
                        "estimated_duration_seconds",
                        None,
                    )
                    or 0,
                    "beat_timing_seconds": dict(
                        getattr(draft_output, "beat_timing_seconds", {}) or {}
                    ),
                    "plan_text": plan_text or "",
                    "target_duration_seconds": target_duration_seconds,
                },
            )

        dispatcher.expected_output = "phase2_implementation"
        dispatcher._print(f"  {_EMOJI['gear']} Phase 2B/5: render implementation pass")
        _emit_status(
            event_callback,
            task_status="running",
            phase="scene",
            message="Phase 2A script draft accepted. Beginning render implementation pass.",
        )
        hook_state.allowed_tools = (
            set(build_opts.allowed_tools) if build_opts.allowed_tools is not None else None
        )
        _emit_phase_enter(
            event_callback,
            phase_id="phase2b",
            phase_name="Render Implementation",
            trace_id=pipeline_trace_id,
        )

        implementation_prompt = build_implementation_prompt(
            user_text,
            target_duration_seconds,
            plan_text,
            build_spec,
            resolved_cwd,
            render_mode=render_mode,
            script_draft_accepted=True,
        )
        write_prompt_artifact(
            output_dir=resolved_cwd,
            phase_id="phase2b",
            phase_name="Render Implementation",
            system_prompt=implementation_system_prompt,
            user_prompt=implementation_prompt,
            inputs={
                **common_debug_inputs,
                "build_spec": _debug_dump(build_spec),
                "plan_text": plan_text,
            },
            options=build_opts,
            options_summary={"output_schema": "phase2_implementation"},
            referenced_artifacts={
                "phase1_planning": "phase1_planning.json",
                "phase2_script_draft": "phase2_script_draft.json",
            },
        )
        implementation_result_summary = await run_phase2_implementation(
            implementation_prompt=implementation_prompt,
            build_options_instance=build_opts,
            dispatcher=dispatcher,
            event_callback=event_callback,
            cli_stderr_lines=_cli_stderr_lines,
            resolved_cwd=resolved_cwd,
        )

        phase2_po = dispatcher.get_pipeline_output()
        phase2_po = apply_phase2_build_spec_defaults(
            phase2_po,
            build_spec=build_spec,
            cwd=resolved_cwd,
            render_mode=render_mode,
            discover_segments=False,
        )
        phase2_issue = implementation_contract_issue(
            phase2_po,
            render_mode=render_mode,
            cwd=resolved_cwd,
        )
        if phase2_issue is not None:
            raise RuntimeError(
                f"Phase 2 implementation output is incomplete. Blocking issue: {phase2_issue}"
            )
        phase2_analysis = analyze_phase2_script(
            scene_file=getattr(phase2_po, "scene_file", None),
            scene_class=getattr(phase2_po, "scene_class", None),
            build_spec=build_spec,
            target_duration_seconds=target_duration_seconds,
            output_dir=resolved_cwd,
        )
        phase2_analysis_path = persist_phase2_script_analysis(
            phase2_analysis,
            output_dir=resolved_cwd,
        )
        dispatcher._print(f"  [BUILD] Phase 2 script analysis persisted: {phase2_analysis_path}")
        update_prompt_artifact(
            output_dir=resolved_cwd,
            phase_id="phase2b",
            output_snapshot={
                "pipeline_output": _debug_dump(phase2_po),
                "phase2_analysis": phase2_analysis.model_dump(),
                "analysis_path": phase2_analysis_path,
                "result_summary": implementation_result_summary,
            },
        )
        if not phase2_analysis.accepted:
            for issue in phase2_analysis.issues:
                dispatcher._print(f"  [BUILD][ERR] {issue}")
            raise RuntimeError(
                "Phase 2 script analysis failed. Blocking issue: "
                + "; ".join(phase2_analysis.issues)
            )
        dispatcher.pipeline_output = phase2_po
        dispatcher.expected_output = "pipeline_output"
        _emit_phase_exit(
            event_callback,
            phase_id="phase2b",
            phase_name="Render Implementation",
            trace_id=pipeline_trace_id,
            turn_count=(
                dispatcher.result_summary.get("turns") if dispatcher.result_summary else None
            ),
            beats_count=len(phase2_po.implemented_beats) if phase2_po else None,
        )
        _emit_phase_enter(
            event_callback,
            phase_id="phase3",
            phase_name="Render+Review",
            trace_id=pipeline_trace_id,
        )
        _emit_status(
            event_callback,
            task_status="running",
            phase="scene",
            message="Structured implementation output accepted. Resolving render output.",
            pipeline_output=phase2_po.model_dump() if phase2_po is not None else None,
        )

        result_summary = merge_result_summaries(
            planning_result_summary,
            script_draft_result_summary,
            implementation_result_summary,
        )
        if result_summary is not None:
            dispatcher.partial_run_turns = result_summary.get("turns")
            dispatcher.partial_run_duration_ms = result_summary.get("duration_ms")
            dispatcher.partial_run_cost_usd = result_summary.get("cost_usd")
            dispatcher.partial_run_cost_cny = result_summary.get("cost_cny")
            dispatcher.partial_run_model_name = result_summary.get("model_name")
            dispatcher.partial_run_pricing_model = result_summary.get("pricing_model")
        dispatcher.partial_run_tool_use_count = dispatcher.tool_use_count
        dispatcher.partial_run_tool_stats = dict(dispatcher.tool_stats)

        # ══════════════════════════════════════════════
        # Phase 3/5: Resolve Render Output + Review
        # ══════════════════════════════════════════════
        po, video_output, review_frames = await run_phase3_render(
            dispatcher=dispatcher,
            hook_state=hook_state,
            user_text=user_text,
            plan_text=plan_text,
            result_summary=result_summary,
            target_duration_seconds=target_duration_seconds,
            resolved_cwd=resolved_cwd,
            system_prompt=render_review_system_prompt,
            quality=quality,
            prompt_file=prompt_file,
            log_callback=log_callback,
            event_callback=event_callback,
            cli_stderr_lines=_cli_stderr_lines,
            render_mode=render_mode,
            no_render_review=no_render_review,
        )
        result_summary = merge_result_summaries(
            result_summary,
            getattr(dispatcher, "partial_render_review_result_summary", None),
        )

        # ══════════════════════════════════════════════
        # Phase 3.5/5: Narration Generation Pass
        # ══════════════════════════════════════════════
        _emit_phase_exit(
            event_callback,
            phase_id="phase3",
            phase_name="Render+Review",
            trace_id=pipeline_trace_id,
            status="ok" if po else "error",
        )
        if po is not None:
            _emit_status(
                event_callback,
                task_status="running",
                phase="render",
                message="Phase 3 render review complete.",
                pipeline_output={
                    "video_output": getattr(po, "video_output", None),
                    "duration_seconds": getattr(po, "duration_seconds", None),
                    "implemented_beats": list(getattr(po, "implemented_beats", []) or []),
                    "build_summary": getattr(po, "build_summary", None) or "",
                    "deviations_from_plan": list(getattr(po, "deviations_from_plan", []) or []),
                    "review_approved": getattr(po, "review_approved", None),
                    "review_summary": getattr(po, "review_summary", None),
                    "plan_text": plan_text or "",
                    "target_duration_seconds": target_duration_seconds,
                },
            )
        _emit_phase_enter(
            event_callback,
            phase_id="phase3_5",
            phase_name="Narration",
            trace_id=pipeline_trace_id,
        )
        dispatcher._print(f"  {_EMOJI['gear']} Phase 3.5/5: narration generation")
        _emit_status(
            event_callback,
            task_status="running",
            phase="narration",
            message="Generating spoken narration for TTS",
        )
        narration_output = await generate_narration(
            user_text=user_text,
            target_duration_seconds=target_duration_seconds,
            plan_text=plan_text,
            po=po,
            video_output=video_output,
            cwd=resolved_cwd,
            system_prompt=narration_system_prompt,
            quality=quality,
            prompt_file=prompt_file,
            log_callback=_counting_log_callback,
            dispatcher=dispatcher,
        )
        narration_text = narration_output.narration
        if po is not None:
            po.narration = narration_text
        update_prompt_artifact(
            output_dir=resolved_cwd,
            phase_id="phase3_5",
            output_snapshot={
                "narration_output": _debug_dump(narration_output),
                "narration_text": narration_text,
            },
        )
        dispatcher._print(
            f"  [NARRATION] Method={narration_output.generation_method}, "
            f"coverage={len(narration_output.beat_coverage)} beats, "
            f"{narration_output.char_count} chars"
        )
        _emit_status(
            event_callback,
            task_status="running",
            phase="narration",
            message="Phase 3.5 narration generation complete.",
            pipeline_output={
                "narration": narration_text or "",
                "beat_to_narration_map": list(
                    getattr(narration_output, "beat_to_narration_map", []) or []
                ),
                "narration_coverage_complete": getattr(
                    narration_output,
                    "narration_coverage_complete",
                    None,
                ),
                "estimated_narration_duration_seconds": getattr(
                    narration_output,
                    "estimated_narration_duration_seconds",
                    None,
                )
                or 0,
                "plan_text": plan_text or "",
                "target_duration_seconds": target_duration_seconds,
                "implemented_beats": list(getattr(po, "implemented_beats", []) or []) if po else [],
            },
        )

        # Merge narration-phase stats
        narration_result_summary = dispatcher.result_summary
        result_summary = merge_result_summaries(result_summary, narration_result_summary)
        if po is not None and result_summary is not None:
            po.run_turns = result_summary.get("turns")
            po.run_duration_ms = result_summary.get("duration_ms")
            po.run_cost_usd = result_summary.get("cost_usd")
            po.run_cost_cny = result_summary.get("cost_cny")
            po.run_model_name = result_summary.get("model_name")
            po.run_pricing_model = result_summary.get("pricing_model")

        # ════════════════════════════════════════════
        # Phase 4+5/5: TTS Synthesis + Video Mux
        # ══════════════════════════════════════════════
        _emit_phase_exit(
            event_callback,
            phase_id="phase3_5",
            phase_name="Narration",
            trace_id=pipeline_trace_id,
        )
        _emit_phase_enter(
            event_callback,
            phase_id="phase4",
            phase_name="TTS+Mux",
            trace_id=pipeline_trace_id,
        )
        if no_tts:
            if po is not None:
                po.final_video_output = video_output
            dispatcher._print(f"\n{_EMOJI['video']} Output silent video: {video_output}")
            dispatcher._print(
                "  [SKIP] Phase 4/5 skipped: TTS synthesis disabled by no_tts option."
            )
            dispatcher._print(
                "  [SKIP] Phase 5/5 skipped: Video muxing requires TTS output and is disabled."
            )
            _emit_phase_exit(
                event_callback,
                phase_id="phase4",
                phase_name="TTS+Mux",
                trace_id=pipeline_trace_id,
                status="cancelled",
            )
            _emit_phase_exit(
                event_callback,
                phase_id="phase5",
                phase_name="Mux",
                trace_id=pipeline_trace_id,
                status="cancelled",
            )
            _emit_status(
                event_callback,
                task_status="running",
                phase="render",
                message="Skipping TTS and mux because no_tts=true. Returning silent render output.",
            )
            return video_output

        audio_result = await run_phase4_tts(
            dispatcher=dispatcher,
            narration_text=narration_text,
            video_output=video_output,
            voice_id=voice_id,
            model=model,
            output_path=output_path,
            po=po,
            user_text=user_text,
            plan_text=plan_text,
            target_duration_seconds=target_duration_seconds,
            bgm_enabled=bgm_enabled,
            bgm_prompt=bgm_prompt,
            preset=preset,
            event_callback=event_callback,
        )
        if po is not None:
            _emit_status(
                event_callback,
                task_status="running",
                phase="tts",
                message="Phase 4 TTS synthesis complete.",
                pipeline_output={
                    "audio_path": getattr(po, "audio_path", None),
                    "tts_mode": getattr(po, "tts_mode", None),
                    "tts_duration_ms": getattr(po, "tts_duration_ms", None),
                    "tts_word_count": getattr(po, "tts_word_count", None),
                    "narration": getattr(po, "narration", None) or "",
                    "target_duration_seconds": target_duration_seconds,
                },
            )

        final_video = await run_phase5_mux(
            dispatcher=dispatcher,
            video_output=video_output,
            audio_result=audio_result,
            output_path=output_path,
            po=po,
            bgm_volume=bgm_volume,
            intro_outro=intro_outro,
            event_callback=event_callback,
        )
        _emit_phase_exit(
            event_callback,
            phase_id="phase4",
            phase_name="TTS",
            trace_id=pipeline_trace_id,
            status="ok",
        )
        _emit_phase_exit(
            event_callback,
            phase_id="phase5",
            phase_name="Mux",
            trace_id=pipeline_trace_id,
            status="ok",
        )
        if po is not None:
            _emit_status(
                event_callback,
                task_status="running",
                phase="mux",
                message="Phase 5 mux complete. Final video ready.",
                pipeline_output={
                    "final_video_output": getattr(po, "final_video_output", None),
                    "video_output": getattr(po, "video_output", None),
                    "duration_seconds": getattr(po, "duration_seconds", None),
                    "subtitle_path": getattr(po, "subtitle_path", None),
                    "bgm_path": getattr(po, "bgm_path", None),
                    "bgm_prompt": getattr(po, "bgm_prompt", None),
                    "audio_path": getattr(po, "audio_path", None),
                    "target_duration_seconds": target_duration_seconds,
                },
            )

        dispatcher._print(f"\n{_EMOJI['check']} Video generation complete: {final_video}")
        return final_video

    except Exception as exc:
        logger.debug("run_pipeline: === SDK QUERY LOOP EXCEPTION ===")
        logger.debug("run_pipeline: exception type=%s", type(exc).__name__)
        logger.debug("run_pipeline: exception message=%s", exc)
        import traceback as _tb

        for _line in _tb.format_exception(type(exc), exc, exc.__traceback__):
            for _ll in _line.rstrip().splitlines():
                logger.debug("run_pipeline: TRACE %s", _ll)
        raise
    finally:
        hook_state.allowed_tools = None
        reset_hook_state(hook_state_token)
