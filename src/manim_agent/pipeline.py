"""Pipeline 编排：Claude Agent SDK → TTS → FFmpeg 的完整执行流程。

包含 run_pipeline() 及其全部辅助函数（options 构建、prompt 包装、
解说生成、render review、PO 元数据填充等）。
"""

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from claude_agent_sdk import query

from . import prompts
from . import music_client, render_review, tts_client, video_builder
from .schemas import Phase1PlanningOutput as ScenePlanOutput
from .dispatcher import _EMOJI, _LOG_SEPARATOR, _MessageDispatcher
from .hooks import activate_hook_state, create_hook_state, reset_hook_state
from .pipeline_config import build_options as _build_options
from .pipeline_config import emit_status as _emit_status
from .pipeline_config import stderr_handler as _stderr_handler
from .pipeline_gates import (
    apply_phase2_build_spec_defaults,
    implementation_contract_issue,
    merge_result_summaries,
)
from .pipeline_narration import generate_narration
from . import pipeline_narration as _pipeline_narration_module
from .pipeline_phases12 import (
    build_implementation_prompt,
    build_scene_plan_prompt,
    run_phase1_planning,
    run_phase2_implementation,
)
from . import pipeline_phases12 as _pipeline_phases12_module
from .pipeline_phases345 import (
    run_phase3_render,
    run_phase4_tts,
    run_phase5_mux,
    run_render_review,
)
from . import pipeline_phases345 as _pipeline_phases345_module

logger = logging.getLogger(__name__)

# ── Re-exported helpers for backward compatibility ─────────────────


# Kept for backward compatibility with test patches:
# tests/test_pipeline_redlights.py patches manim_agent.pipeline._stderr_handler
# tests/test_main_dispatcher_pipeline.py patches manim_agent.pipeline._run_render_review
stderr_handler = _stderr_handler
_run_render_review = run_render_review

# ── Main Pipeline ────────────────────────────────────────────────────


async def run_pipeline(
    user_text: str,
    output_path: str,
    voice_id: str = "female-tianmei",
    model: str = "speech-2.8-hd",
    quality: str = "high",
    no_tts: bool = False,
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
    full_system_prompt = prompts.get_prompt(
        user_text="",
        preset=preset,
        quality=quality,
        cwd=resolved_cwd,
    )
    system_prompt = full_system_prompt

    planning_options = _build_options(
        cwd=resolved_cwd,
        system_prompt=system_prompt,
        max_turns=min(max_turns, 16),
        prompt_file=prompt_file,
        quality=quality,
        log_callback=log_callback,
        output_format=ScenePlanOutput.output_format_schema(),
        use_default_output_format=False,
        allowed_tools=["Read", "Glob", "Grep"],
    )
    build_opts = _build_options(
        cwd=resolved_cwd,
        system_prompt=system_prompt,
        max_turns=max_turns,
        prompt_file=prompt_file,
        quality=quality,
        log_callback=log_callback,
    )

    hook_state = create_hook_state(event_callback=event_callback)
    hook_state_token = activate_hook_state(hook_state)
    dispatcher = _MessageDispatcher(
        verbose=True,
        log_callback=log_callback,
        output_cwd=resolved_cwd,
        hook_state=hook_state,
    )
    if event_callback is not None:
        dispatcher.event_callback = event_callback

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
        planning_result_summary: dict[str, Any] | None = None
        planning_prompt = build_scene_plan_prompt(
            user_text,
            target_duration_seconds,
            resolved_cwd,
        )
        planning_result_summary = await run_phase1_planning(
            planning_prompt=planning_prompt,
            planning_options=planning_options,
            dispatcher=dispatcher,
            event_callback=event_callback,
        )

        plan_text = dispatcher.partial_plan_text
        build_spec = getattr(dispatcher, "partial_build_spec", None)
        dispatcher.partial_render_mode = render_mode
        dispatcher.partial_segment_render_complete = False
        dispatcher._print(f"  {_EMOJI['gear']} Phase 2/5: implementation pass")
        if build_opts.allowed_tools:
            dispatcher._print(f"  [SYS] Allowed tools: {', '.join(build_opts.allowed_tools)}")

        # ══════════════════════════════════════════════
        # Phase 2/5: Implementation Pass
        # ══════════════════════════════════════════════
        implementation_prompt = build_implementation_prompt(
            user_text,
            target_duration_seconds,
            plan_text,
            build_spec,
            resolved_cwd,
            render_mode=render_mode,
        )
        implementation_result_summary = await run_phase2_implementation(
            implementation_prompt=implementation_prompt,
            build_options_instance=build_opts,
            dispatcher=dispatcher,
            event_callback=event_callback,
            cli_stderr_lines=_cli_stderr_lines,
        )

        if _dispatcher_ref is not None:
            _dispatcher_ref.append(dispatcher)

        phase2_po = dispatcher.get_pipeline_output()
        phase2_po = apply_phase2_build_spec_defaults(
            phase2_po,
            build_spec=build_spec,
            cwd=resolved_cwd,
            render_mode=render_mode,
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

        result_summary = merge_result_summaries(
            planning_result_summary,
            implementation_result_summary,
        )
        if result_summary is not None:
            dispatcher.partial_run_turns = result_summary.get("turns")
            dispatcher.partial_run_duration_ms = result_summary.get("duration_ms")
            dispatcher.partial_run_cost_usd = result_summary.get("cost_usd")
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
            system_prompt=system_prompt,
            quality=quality,
            prompt_file=prompt_file,
            log_callback=log_callback,
            event_callback=event_callback,
            cli_stderr_lines=_cli_stderr_lines,
            render_mode=render_mode,
        )

        # ══════════════════════════════════════════════
        # Phase 3.5/5: Narration Generation Pass
        # ══════════════════════════════════════════════
        dispatcher._print(f"  {_EMOJI['gear']} Phase 3.5/5: narration generation")
        _emit_status(
            event_callback,
            task_status="running",
            phase="narration",
            message="Generating spoken narration for TTS",
        )
        narration_text = await generate_narration(
            user_text=user_text,
            target_duration_seconds=target_duration_seconds,
            plan_text=plan_text,
            po=po,
            video_output=video_output,
            cwd=resolved_cwd,
            system_prompt=system_prompt,
            quality=quality,
            prompt_file=prompt_file,
            log_callback=_counting_log_callback,
            dispatcher=dispatcher,
        )
        if po is not None:
            po.narration = narration_text

        # Merge narration-phase stats
        narration_result_summary = dispatcher.result_summary
        result_summary = merge_result_summaries(result_summary, narration_result_summary)
        if po is not None and result_summary is not None:
            po.run_turns = result_summary.get("turns")
            po.run_duration_ms = result_summary.get("duration_ms")
            po.run_cost_usd = result_summary.get("cost_usd")

        # ══════════════════════════════════════════════
        # Phase 4+5/5: TTS Synthesis + Video Mux
        # ══════════════════════════════════════════════
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
        reset_hook_state(hook_state_token)
