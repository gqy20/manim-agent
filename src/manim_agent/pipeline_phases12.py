"""Phase 1 (planning) and Phase 2 (implementation) pipeline functions."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from claude_agent_sdk import query

from .dispatcher import _MessageDispatcher
from .pipeline_config import emit_status
from .pipeline_events import PipelineEvent
from .prompt_builder import format_target_duration
from .schemas import Phase1PlanningOutput, Phase2ImplementationOutput, PipelineOutput


def build_scene_plan_prompt(
    user_text: str,
    target_duration_seconds: int,
    preset: str = "default",
    quality: str = "high",
    render_mode: str = "full",
) -> str:
    """Build a planning-only prompt that returns only Phase 1 structured output."""
    normalized = user_text.strip()
    target_duration = format_target_duration(target_duration_seconds)
    render_mode = (render_mode or "full").strip().lower() or "full"
    guidance = (
        "\n\nPlanning pass only:\n"
        f"- Target final video duration: about {target_duration}.\n"
        f"- Preset: {preset}.\n"
        f"- Quality target: {quality}.\n"
        f"- Downstream render mode: {render_mode}.\n"
        "- Return the Phase 1 `build_spec` through the configured structured_output schema.\n"
        "- Do not use Bash, Read, Glob, Grep, ls, find, or path probes in this pass.\n"
        "- Do not write, edit, or render any code in this pass.\n"
        "- Keep the structured plan compact and implementation-ready.\n"
    )
    if render_mode == "segments":
        guidance += (
            "- Plan one segment-required beat per major teaching step and use stable beat ids "
            "that can become segment filenames later.\n"
        )
    return f"{normalized}{guidance}" if normalized else guidance.strip()


def render_build_spec_markdown(
    scene_plan_output: Phase1PlanningOutput,
    *,
    target_duration_seconds: int,
) -> str:
    """Render the structured Phase 1 contract into deterministic Markdown for humans/Phase 2."""
    spec = scene_plan_output.build_spec
    lines = [
        "## Mode",
        spec.mode,
        "",
        "## Learning Goal",
        spec.learning_goal,
        "",
        "## Audience",
        spec.audience,
        "",
        "## Beat List",
    ]
    for index, beat in enumerate(spec.beats, start=1):
        required = ", ".join(beat.required_elements) if beat.required_elements else "none"
        segment_required = "yes" if beat.segment_required else "no"
        lines.extend(
            [
                f"{index}. {beat.title}",
                f"   - id: `{beat.id}`",
                f"   - visual_goal: {beat.visual_goal}",
                f"   - narration_intent: {beat.narration_intent}",
                f"   - target_duration_seconds: {beat.target_duration_seconds:g}",
                f"   - required_elements: {required}",
                f"   - segment_required: {segment_required}",
            ]
        )
    lines.extend(
        [
            "",
            "## Build Handoff",
            f"Implement the ordered `build_spec` beats for a target duration of "
            f"{target_duration_seconds} seconds.",
            "Keep the beat ids stable and report implementation deviations explicitly.",
        ]
    )
    return "\n".join(lines).strip()


def build_phase1_pipeline_output_snapshot(
    scene_plan_output: Phase1PlanningOutput,
    *,
    target_duration_seconds: int,
    plan_text: str,
) -> dict[str, Any]:
    """Build the minimal DB/API snapshot produced by Phase 1."""
    return {
        "phase1_planning": scene_plan_output.model_dump(),
        "target_duration_seconds": target_duration_seconds,
        "plan_text": plan_text,
    }


def _normalize_phase1_output(
    scene_plan_output: Phase1PlanningOutput,
    *,
    target_duration_seconds: int,
    dispatcher: _MessageDispatcher,
) -> Phase1PlanningOutput:
    """Normalize deterministic Phase 1 fields owned by the pipeline."""
    if scene_plan_output.build_spec.target_duration_seconds != target_duration_seconds:
        dispatcher._print(
            "  [WARN] build_spec.target_duration_seconds did not match the request; "
            f"using {target_duration_seconds}."
        )
        scene_plan_output.build_spec.target_duration_seconds = target_duration_seconds
    return scene_plan_output


def persist_phase1_planning_output(
    scene_plan_output: Phase1PlanningOutput,
    *,
    resolved_cwd: str,
) -> str:
    """Persist the accepted Phase 1 contract immediately after validation."""
    output_path = Path(resolved_cwd).resolve() / "phase1_planning.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(scene_plan_output.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(output_path)


def persist_phase2_implementation_output(
    phase2_output: Phase2ImplementationOutput,
    *,
    resolved_cwd: str,
) -> str:
    """Persist the accepted Phase 2 implementation contract after validation."""
    output_path = Path(resolved_cwd).resolve() / "phase2_implementation.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(phase2_output.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(output_path)


def build_pipeline_output_from_phase2(
    phase2_output: Phase2ImplementationOutput,
    *,
    dispatcher: _MessageDispatcher,
    target_duration_seconds: int | None,
    plan_text: str | None,
) -> PipelineOutput:
    """Project Phase 2's stage output into the pipeline-wide working model."""
    return PipelineOutput(
        video_output=phase2_output.video_output,
        scene_file=phase2_output.scene_file,
        scene_class=phase2_output.scene_class,
        narration=phase2_output.narration,
        implemented_beats=list(phase2_output.implemented_beats),
        build_summary=phase2_output.build_summary,
        deviations_from_plan=list(phase2_output.deviations_from_plan),
        render_mode=phase2_output.render_mode,
        segment_render_complete=phase2_output.segment_render_complete,
        segment_video_paths=list(phase2_output.segment_video_paths),
        source_code=phase2_output.source_code,
        target_duration_seconds=target_duration_seconds,
        plan_text=plan_text,
        phase1_planning=dispatcher.get_scene_plan_output(),
        phase2_implementation=phase2_output,
    )


def build_implementation_prompt(
    user_text: str,
    target_duration_seconds: int,
    plan_text: str,
    build_spec: dict[str, Any] | None = None,
    cwd: str | None = None,
    render_mode: str = "full",
) -> str:
    """Build the implementation prompt after a planning pass has been accepted."""
    normalized = user_text.strip()
    target_duration = format_target_duration(target_duration_seconds)
    render_mode = render_mode.strip().lower() or "full"
    render_guidance = (
        "- Render mode: full.\n"
        "- The primary visual deliverable is one full-length `video_output` MP4.\n"
        "- You may create helper clips during debugging, but the final structured "
        "output must center on the single main render.\n"
        "- In structured_output, include `video_output` with the rendered MP4 path.\n"
    )
    if render_mode == "segments":
        render_guidance = (
            "- Render mode: segments.\n"
            "- The primary visual deliverables are beat-level MP4 files such as "
            "`segments/beat_001.mp4`, `segments/beat_002.mp4`, in beat order.\n"
            "- In structured_output, include `segment_video_paths` with the ordered "
            "segment paths that were actually rendered.\n"
            "- In structured_output, include `render_mode` as `segments` and "
            "`segment_render_complete` as true only when every planned beat segment exists.\n"
            "- Do not treat a single full-length `video_output` as the primary "
            "deliverable in this mode; if you also produce one, treat it as a "
            "convenience artifact.\n"
            "- If you cannot produce the real beat-level MP4 files, stop and fail "
            "instead of silently returning a degraded full-render result.\n"
            "- Do not mark `segment_render_complete` true as a placeholder.\n"
        )
    guidance = (
        "\n\nImplementation pass:\n"
        f"- Target final video duration: about {target_duration}.\n"
        "- The Phase 1 `build_spec` is authoritative. Implement from it instead of "
        "creating a new plan.\n"
        "- Preserve the planned beat order unless debugging requires a very small fix.\n"
        "- Do not begin with a fresh planning pass; begin implementation from the approved plan.\n"
        f"{render_guidance}"
        "- In structured_output, include `implemented_beats` as the ordered "
        "beat titles that were actually built.\n"
        "- In structured_output, include `build_summary` as a short summary "
        "of what the build phase implemented.\n"
        "- In structured_output, include `deviations_from_plan` as an array, even if it is empty.\n"
        "- Focus your structured_output effort on the implementation facts that only "
        "you know: what beats were actually built, what deviated, and the final "
        "narration text.\n"
        "- The pipeline will derive beat-level narration bookkeeping, coverage flags, "
        "and estimated narration duration from the approved build spec.\n"
        "- In `segments` mode, prioritize writing the real beat files to canonical "
        "paths like `segments/<beat_id>.mp4` and report those paths in structured_output.\n"
        "- Do not leave `implemented_beats` empty.\n"
        "- Do not omit `build_summary`.\n"
        "- Keep every file inside the task directory only.\n"
        "- Write the main script to scene.py unless multiple files are truly necessary.\n"
        "- Use GeneratedScene as the main Manim Scene class unless "
        "the user explicitly asks otherwise.\n"
        "- Run Manim directly from the task directory with `manim scene.py GeneratedScene`.\n"
        "- Do not use absolute repository paths, do not cd to the repo root, "
        "and do not invoke `.venv/Scripts/python` directly.\n"
    )
    if build_spec is not None:
        guidance += (
            "\nApproved Phase 1 build_spec (JSON):\n"
            f"{json.dumps(build_spec, ensure_ascii=False, indent=2)}\n"
        )
    else:
        guidance += (
            "\nApproved build plan/context:\n"
            f"{plan_text}\n"
        )
    return f"{normalized}{guidance}" if normalized else guidance.strip()


async def run_phase1_planning(
    planning_prompt: str,
    target_duration_seconds: int,
    planning_options: Any,
    system_prompt: str,
    quality: str,
    prompt_file: str | None,
    log_callback: Callable[[str], None] | None,
    resolved_cwd: str,
    dispatcher: _MessageDispatcher,
    event_callback: Callable[[PipelineEvent], None] | None,
) -> dict[str, Any]:
    """Execute Phase 1: scene planning pass."""
    planning_result_summary: dict[str, Any] | None = None

    async for message in query(prompt=planning_prompt, options=planning_options):
        dispatcher.dispatch(message)

    planning_result_summary = dispatcher.result_summary

    scene_plan_output = dispatcher.get_scene_plan_output()
    if scene_plan_output is None:
        diagnostics = dispatcher.get_phase1_failure_diagnostics()
        dispatcher._print("")
        dispatcher._print("  [ERR] Structured Phase 1 planning output missing or invalid.")
        if diagnostics.get("scene_plan_validation_error"):
            dispatcher._print(
                "  [ERR] scene_plan_validation_error="
                f"{diagnostics['scene_plan_validation_error']}"
            )
        dispatcher._print(
            "  [ERR] raw_structured_output_present="
            f"{diagnostics.get('raw_structured_output_present')} "
            f"type={diagnostics.get('raw_structured_output_type')}"
        )
        raise RuntimeError(
            "Phase 1 planning did not return the required structured build_spec output."
        )

    scene_plan_output = _normalize_phase1_output(
        scene_plan_output,
        target_duration_seconds=target_duration_seconds,
        dispatcher=dispatcher,
    )
    plan_text = render_build_spec_markdown(
        scene_plan_output,
        target_duration_seconds=target_duration_seconds,
    )
    phase1_output_path = persist_phase1_planning_output(
        scene_plan_output,
        resolved_cwd=resolved_cwd,
    )
    dispatcher.partial_build_spec = scene_plan_output.build_spec.model_dump()
    dispatcher.partial_target_duration_seconds = target_duration_seconds
    dispatcher.partial_plan_text = plan_text
    dispatcher.phase1_output_path = phase1_output_path
    dispatcher.phase1_diagnostics_snapshot = {
        **dispatcher.get_phase1_failure_diagnostics(),
        "accepted": True,
        "output_path": phase1_output_path,
        "build_spec_beat_count": len(scene_plan_output.build_spec.beats),
    }
    dispatcher._print("  [PLAN] Structured build_spec accepted.")
    dispatcher._print(f"  [PLAN] Phase 1 contract persisted: {phase1_output_path}")
    dispatcher._print("  [PROGRESS] Phase 2/5: implementation pass")
    if planning_options.allowed_tools:
        dispatcher._print(f"  [SYS] Allowed tools: {', '.join(planning_options.allowed_tools)}")

    emit_status(
        event_callback,
        task_status="running",
        phase="scene",
        message="Structured build_spec accepted. Beginning implementation pass.",
        pipeline_output=(
            build_phase1_pipeline_output_snapshot(
                scene_plan_output,
                target_duration_seconds=target_duration_seconds,
                plan_text=plan_text,
            )
            if event_callback is not None
            else None
        ),
    )

    return planning_result_summary or {}


async def run_phase2_implementation(
    implementation_prompt: str,
    build_options_instance: Any,
    dispatcher: _MessageDispatcher,
    event_callback: Callable[[PipelineEvent], None] | None,
    cli_stderr_lines: list[str],
    resolved_cwd: str,
) -> dict[str, Any]:
    """Execute Phase 2: implementation pass."""
    async for message in query(prompt=implementation_prompt, options=build_options_instance):
        dispatcher.dispatch(message)
        if dispatcher.implementation_started:
            if not getattr(dispatcher, "partial_build_spec", None):
                dispatcher._print("")
                dispatcher._print("[ERR] Blocking implementation before Phase 1 build_spec.")
                if dispatcher.implementation_start_reason:
                    dispatcher._print(
                        f"  First implementation step: {dispatcher.implementation_start_reason}"
                    )
                dispatcher._print(
                    "  Emit the required structured Phase 1 build_spec before writing scene.py, "
                    "editing Python files, or running Manim."
                )
                raise RuntimeError(
                    "Claude began implementation before emitting the required Phase 1 build_spec"
                )

    phase2_output = dispatcher.get_phase2_implementation_output()
    if phase2_output is None:
        raw_type = (
            type(dispatcher.raw_structured_output).__name__
            if dispatcher.raw_structured_output is not None
            else None
        )
        dispatcher._print("")
        dispatcher._print("  [ERR] Structured Phase 2 implementation output missing or invalid.")
        dispatcher._print(
            "  [ERR] raw_structured_output_present="
            f"{dispatcher.raw_structured_output is not None} "
            f"type={raw_type}"
        )
        raise RuntimeError(
            "Phase 2 implementation did not return the required structured implementation output."
        )

    phase2_output_path = persist_phase2_implementation_output(
        phase2_output,
        resolved_cwd=resolved_cwd,
    )
    dispatcher.phase2_output_path = phase2_output_path
    dispatcher.pipeline_output = build_pipeline_output_from_phase2(
        phase2_output,
        dispatcher=dispatcher,
        target_duration_seconds=getattr(dispatcher, "partial_target_duration_seconds", None),
        plan_text=getattr(dispatcher, "partial_plan_text", None),
    )
    dispatcher._sync_compat_attrs()
    dispatcher._print("  [BUILD] Structured implementation output accepted.")
    dispatcher._print(f"  [BUILD] Phase 2 contract persisted: {phase2_output_path}")

    return dispatcher.result_summary or {}
