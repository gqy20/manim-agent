"""Phase 1 (planning) and Phase 2 (implementation) pipeline functions."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from claude_agent_sdk import query

from .dispatcher import _MessageDispatcher
from .pipeline_config import emit_status
from .pipeline_events import PipelineEvent
from .prompt_builder import format_target_duration
from .schemas import (
    Phase1PlanningOutput,
    Phase2ImplementationOutput,
    Phase2ScriptDraftOutput,
    PipelineOutput,
)


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


def persist_phase2_script_draft_output(
    draft_output: Phase2ScriptDraftOutput,
    *,
    resolved_cwd: str,
) -> str:
    """Persist the accepted Phase 2A script draft contract."""
    output_path = Path(resolved_cwd).resolve() / "phase2_script_draft.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(draft_output.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(output_path)


def freeze_phase2_artifacts(
    phase2_output: Phase2ImplementationOutput,
    *,
    resolved_cwd: str,
) -> Phase2ImplementationOutput:
    """Copy Phase 2 executable artifacts to stable top-level task files.

    Manim writes videos under cache-like ``media/`` directories that backend
    cleanup removes. Stable copies make Phase 2 independently auditable after
    later phases fail or cleanup runs.
    """
    root = Path(resolved_cwd).resolve()
    normalized = phase2_output.model_copy(deep=True)

    if normalized.scene_file:
        scene_path = Path(normalized.scene_file)
        if not scene_path.is_absolute():
            scene_path = root / scene_path
        if scene_path.exists():
            frozen_scene = root / "phase2_scene.py"
            if scene_path.resolve() != frozen_scene.resolve():
                shutil.copy2(scene_path, frozen_scene)
            normalized.scene_file = str(frozen_scene)

    if normalized.video_output:
        video_path = Path(normalized.video_output)
        if not video_path.is_absolute():
            video_path = root / video_path
        if video_path.exists():
            frozen_video = root / "phase2_video.mp4"
            if video_path.resolve() != frozen_video.resolve():
                shutil.copy2(video_path, frozen_video)
            normalized.video_output = str(frozen_video)

    return normalized


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
    script_draft_accepted: bool = False,
) -> str:
    """Build the implementation prompt after a planning pass has been accepted."""
    normalized = user_text.strip()
    target_duration = format_target_duration(target_duration_seconds)
    render_mode = render_mode.strip().lower() or "full"
    render_guidance = "- Render mode: full — deliver one `video_output` MP4.\n"
    if render_mode == "segments":
        render_guidance = (
            "- Render mode: segments — deliver beat-level MP4s like "
            "`segments/beat_001.mp4`, `segments/beat_002.mp4` in beat order.\n"
            "- Report ordered paths in `segment_video_paths`. Set "
            "`segment_render_complete=true` only when all segments exist.\n"
        )
    guidance = (
        "\n\nPhase 2B — render implementation pass:\n"
        f"- Target final video duration: about {target_duration}.\n"
        "- The Phase 1 `build_spec` is authoritative. Implement from it.\n"
        f"{render_guidance}"
        "- Coding rules, beat structure, CJK handling, animation patterns, and "
        "component usage are ALL in the `/scene-build` skill — read it first.\n"
        "- The `/scene-direction` skill covers pacing and rhythm decisions.\n"
        "- The `/layout-safety` skill covers overlap auditing for dense beats.\n"
        "- The `/narration-sync` skill covers generating aligned narration text.\n"
        "- The `/render-review` skill covers post-render visual quality checks.\n"
    )
    if script_draft_accepted:
        guidance += (
            "- A local script-draft gate has already accepted the beat-first structure in "
            "`scene.py`. Continue from that script, preserve the exact beat methods and "
            "`construct()` order, then render and repair only implementation/render issues.\n"
        )
    if build_spec is not None:
        guidance += (
            "\nApproved Phase 1 build_spec (JSON):\n"
            f"{json.dumps(build_spec, ensure_ascii=False, indent=2)}\n"
        )
    else:
        guidance += f"\nApproved build plan/context:\n{plan_text}\n"
    return f"{normalized}{guidance}" if normalized else guidance.strip()


def build_phase2_script_draft_prompt(
    user_text: str,
    target_duration_seconds: int,
    build_spec: dict[str, Any] | None,
    cwd: str | None = None,
    render_mode: str = "full",
) -> str:
    """Build the Phase 2A prompt that writes a beat-first script before rendering."""
    normalized = user_text.strip()
    target_duration = format_target_duration(target_duration_seconds)
    render_mode = render_mode.strip().lower() or "full"
    guidance = (
        "\n\nPhase 2A — script draft pass (no rendering):\n"
        f"- Target final video duration: about {target_duration}.\n"
        f"- Downstream render mode: {render_mode}.\n"
        "- Coding rules, beat structure, CJK handling, animation patterns, and "
        "component usage are ALL in the `/scene-build` skill — read it first.\n"
        "- The `/scene-direction` skill covers pacing and rhythm decisions.\n"
        "- The `/layout-safety` skill covers overlap auditing for dense beats.\n"
    )
    if cwd:
        guidance += f"- Task directory: {cwd}\n"
    if build_spec is not None:
        guidance += (
            "\nApproved Phase 1 build_spec (JSON):\n"
            f"{json.dumps(build_spec, ensure_ascii=False, indent=2)}\n"
        )
    return f"{normalized}{guidance}" if normalized else guidance.strip()


def build_phase2_script_repair_prompt(
    user_text: str,
    target_duration_seconds: int,
    build_spec: dict[str, Any] | None,
    analysis: dict[str, Any],
    cwd: str | None = None,
    render_mode: str = "full",
) -> str:
    """Build a focused repair prompt for a rejected Phase 2A script draft."""
    normalized = user_text.strip()
    target_duration = format_target_duration(target_duration_seconds)
    render_mode = render_mode.strip().lower() or "full"
    guidance = (
        "\n\nPhase 2A repair pass (no rendering):\n"
        f"- Target final video duration remains about {target_duration}.\n"
        f"- Downstream render mode remains {render_mode}.\n"
        "- Read the existing `scene.py`, fix only the blocking script-analysis issues, "
        "and preserve the approved beat structure and visual design.\n"
        "- Do NOT render, run Manim, run FFmpeg, create videos, or start a fresh plan.\n"
        "- Keep the fix narrow: syntax errors, missing beat methods, construct order, "
        "or explicit timing gates reported below.\n"
        "- Before submitting, self-check that `scene.py` is valid Python. In particular, "
        "never place another positional animation after a keyword argument inside "
        "`self.play(...)`; either put all animations before `run_time=` or split the "
        "animations into separate `self.play` calls.\n"
        "- Return SDK structured output ONLY via the `phase2_script_draft` schema.\n"
    )
    if cwd:
        guidance += f"- Task directory: {cwd}\n"
    if build_spec is not None:
        guidance += (
            "\nApproved Phase 1 build_spec (JSON):\n"
            f"{json.dumps(build_spec, ensure_ascii=False, indent=2)}\n"
        )
    guidance += (
        "\nBlocking script-analysis result to repair:\n"
        f"{json.dumps(analysis, ensure_ascii=False, indent=2)}\n"
    )
    return f"{normalized}{guidance}" if normalized else guidance.strip()


def reset_phase2_script_draft_capture(dispatcher: _MessageDispatcher) -> None:
    """Clear Phase 2A structured-output capture before a repair pass."""
    dispatcher.phase2_script_draft_output = None
    dispatcher._phase2_script_draft_output_candidate = None
    dispatcher.raw_structured_output = None
    dispatcher.raw_result_text = None
    dispatcher._result_message = None


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
                f"  [ERR] scene_plan_validation_error={diagnostics['scene_plan_validation_error']}"
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


async def run_phase2_script_draft(
    script_draft_prompt: str,
    script_draft_options_instance: Any,
    dispatcher: _MessageDispatcher,
    resolved_cwd: str,
) -> dict[str, Any]:
    """Execute Phase 2A: write a beat-first script before rendering."""
    async for message in query(prompt=script_draft_prompt, options=script_draft_options_instance):
        dispatcher.dispatch(message)
        if dispatcher.implementation_started and not getattr(
            dispatcher, "partial_build_spec", None
        ):
            raise RuntimeError(
                "Claude began implementation before emitting the required Phase 1 build_spec"
            )

    draft_output = dispatcher.get_phase2_script_draft_output()
    if draft_output is None:
        raw_type = (
            type(dispatcher.raw_structured_output).__name__
            if dispatcher.raw_structured_output is not None
            else None
        )
        dispatcher._print("")
        dispatcher._print("  [ERR] Structured Phase 2A script draft output missing or invalid.")
        dispatcher._print(
            "  [ERR] raw_structured_output_present="
            f"{dispatcher.raw_structured_output is not None} "
            f"type={raw_type}"
        )
        raise RuntimeError(
            "Phase 2A script draft did not return the required structured script output."
        )

    draft_path = persist_phase2_script_draft_output(
        draft_output,
        resolved_cwd=resolved_cwd,
    )
    dispatcher.phase2_script_draft_output = draft_output
    dispatcher.phase2_script_draft_path = draft_path
    dispatcher._print("  [BUILD] Structured script draft output accepted.")
    dispatcher._print(f"  [BUILD] Phase 2A script draft persisted: {draft_path}")
    return dispatcher.result_summary or {}


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

    draft_output = getattr(dispatcher, "phase2_script_draft_output", None)
    if isinstance(draft_output, Phase2ScriptDraftOutput):
        if not phase2_output.scene_file:
            phase2_output.scene_file = draft_output.scene_file
        if not phase2_output.scene_class:
            phase2_output.scene_class = draft_output.scene_class
        if not phase2_output.source_code:
            phase2_output.source_code = draft_output.source_code

    phase2_output = freeze_phase2_artifacts(
        phase2_output,
        resolved_cwd=resolved_cwd,
    )
    dispatcher.phase2_implementation_output = phase2_output
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
