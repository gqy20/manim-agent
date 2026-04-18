"""Phase 1 (planning) and Phase 2 (implementation) pipeline functions."""

from __future__ import annotations

from collections.abc import Callable
import json
from typing import Any

from claude_agent_sdk import query

from .schemas import Phase1PlanningOutput as ScenePlanOutput
from .dispatcher import _MessageDispatcher
from .pipeline_config import emit_status, resolve_plugin_dir
from .pipeline_events import PipelineEvent
from .pipeline_gates import (
    extract_visible_scene_plan_text,
    has_scene_plan_skill_signature,
    has_visible_scene_plan,
)
from .prompt_builder import format_target_duration


def build_scene_plan_prompt(
    user_text: str,
    target_duration_seconds: int,
    cwd: str | None = None,
) -> str:
    """Build a planning-only prompt that must stop after the visible plan."""
    normalized = user_text.strip()
    target_duration = format_target_duration(target_duration_seconds)
    plugin_dir = resolve_plugin_dir(cwd)
    headings = (
        "`Mode`, `Learning Goal`, `Audience`, `Beat List`, "
        "`Narration Outline`, `Visual Risks`, and `Build Handoff`"
    )
    guidance = (
        "\n\nPlanning pass only:\n"
        f"- Target final video duration: about {target_duration}.\n"
        f"- Use the runtime-injected `scene-plan` skill from the plugin rooted at "
        f"`{plugin_dir}` and stop after producing the visible plan.\n"
        "- The plugin location is a read-only runtime reference, not the writable task directory.\n"
        "- Do not use Bash, Read, ls, find, or path probes to verify plugin files in this pass.\n"
        "- Do not write, edit, or render any code in this pass.\n"
        "- Use only lightweight reference reads if needed.\n"
        f"- Return a Markdown plan with these exact section headings: {headings}.\n"
        "- Also return structured_output that conforms to the Phase 1 `build_spec` contract.\n"
        "- The structured `build_spec` must include stable beat ids, per-beat visual goals, narration intents, target durations, required elements, and whether each beat requires a segment.\n"
        "- Keep the plan compact and implementation-ready.\n"
    )
    return f"{normalized}{guidance}" if normalized else guidance.strip()


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
    plugin_dir = resolve_plugin_dir(cwd)
    render_mode = render_mode.strip().lower() or "full"
    render_guidance = (
        "- Render mode: full.\n"
        "- The primary visual deliverable is one full-length `video_output` MP4.\n"
        "- You may create helper clips during debugging, but the final structured output must center on the single main render.\n"
    )
    if render_mode == "segments":
        render_guidance = (
            "- Render mode: segments.\n"
            "- The primary visual deliverables are beat-level MP4 files such as `segments/beat_001.mp4`, `segments/beat_002.mp4`, in beat order.\n"
            "- In structured_output, include `segment_video_paths` with the ordered segment paths that were actually rendered.\n"
            "- In structured_output, include `render_mode` as `segments` and `segment_render_complete` as true only when every planned beat segment exists.\n"
            "- Do not treat a single full-length `video_output` as the primary deliverable in this mode; if you also produce one, treat it as a convenience artifact.\n"
            "- If you cannot produce the real beat-level MP4 files, stop and fail instead of silently returning a degraded full-render result.\n"
            "- Do not mark `segment_render_complete` true as a placeholder.\n"
        )
    guidance = (
        "\n\nImplementation pass:\n"
        f"- Target final video duration: about {target_duration}.\n"
        "- The visible scene plan below is approved. "
        "Implement from it instead of creating a new plan.\n"
        "- The structured build specification below is authoritative. Do not redesign the beat structure during implementation.\n"
        "- Continue using the runtime-injected `manim-production` plugin "
        f"rooted at `{plugin_dir}`.\n"
        "- Use `scene-build`, `scene-direction`, `layout-safety`, `narration-sync`, "
        "and `render-review` through that injected plugin workflow.\n"
        "- Use `layout-safety` as an advisory audit for dense beats and interpret warnings.\n"
        "- The plugin location is a read-only runtime reference, not the writable task directory.\n"
        "- Do not use shell or filesystem probes to verify plugin files during implementation.\n"
        "- Preserve the planned beat order unless debugging requires a very small fix.\n"
        "- Do not begin with a fresh planning pass; begin implementation from the approved plan.\n"
        f"{render_guidance}"
        "- In structured_output, include `implemented_beats` as the ordered "
        "beat titles that were actually built.\n"
        "- In structured_output, include `build_summary` as a short summary "
        "of what the build phase implemented.\n"
        "- In structured_output, include `deviations_from_plan` as an array, even if it is empty.\n"
        "- Focus your structured_output effort on the implementation facts that only you know: what beats were actually built, what deviated, and the final narration text.\n"
        "- The pipeline will derive beat-level narration bookkeeping, coverage flags, and estimated narration duration from the approved build spec when possible.\n"
        "- In `segments` mode, prioritize writing the real beat files to canonical paths like `segments/<beat_id>.mp4`; the pipeline can discover those files automatically.\n"
        "- Do not leave `implemented_beats` empty.\n"
        "- Do not omit `build_summary`.\n"
        "- Keep every file inside the task directory only.\n"
        "- Write the main script to scene.py unless multiple files are truly necessary.\n"
        "- Use GeneratedScene as the main Manim Scene class unless "
        "the user explicitly asks otherwise.\n"
        "- Run Manim directly from the task directory with `manim scene.py GeneratedScene`.\n"
        "- Do not use absolute repository paths, do not cd to the repo root, "
        "and do not invoke `.venv/Scripts/python` directly.\n"
        "- Return structured_output.narration as natural Simplified Chinese "
        "unless the user explicitly requests another language.\n"
        "- Make the narration spoken and synchronized with the animation, and cover the full flow "
        "rather than collapsing into a one-sentence summary.\n"
        "\nApproved visible scene plan:\n"
        f"{plan_text}\n"
    )
    if build_spec is not None:
        guidance += (
            "\nApproved structured build specification (JSON):\n"
            f"{json.dumps(build_spec, ensure_ascii=False, indent=2)}\n"
        )
    return f"{normalized}{guidance}" if normalized else guidance.strip()


async def run_phase1_planning(
    planning_prompt: str,
    planning_options: Any,
    dispatcher: _MessageDispatcher,
    event_callback: Callable[[PipelineEvent], None] | None,
) -> dict[str, Any]:
    """Execute Phase 1: scene planning pass."""
    planning_result_summary: dict[str, Any] | None = None

    async for message in query(prompt=planning_prompt, options=planning_options):
        dispatcher.dispatch(message)

    planning_result_summary = dispatcher.result_summary

    if not has_visible_scene_plan(dispatcher.collected_text):
        dispatcher._print("")
        dispatcher._print("[ERR] Missing required scene plan before implementation.")
        dispatcher._print(
            "  The assistant must emit a visible planning pass with Mode, Learning Goal,"
        )
        dispatcher._print(
            "  Audience, Beat List, Narration Outline, Visual Risks, and Build Handoff"
        )
        raise RuntimeError(
            "Claude skipped the required scene-plan pass. "
            "A visible planning scaffold is mandatory before implementation."
        )

    if not has_scene_plan_skill_signature(dispatcher.collected_text):
        dispatcher._print("")
        dispatcher._print(
            "  [WARN] Visible plan does not include the optional scene-plan signature."
        )
        dispatcher._print("  Continuing because the visible plan itself is present.")

    plan_text = extract_visible_scene_plan_text(dispatcher.collected_text)
    scene_plan_output = dispatcher.get_scene_plan_output()
    if scene_plan_output is None:
        raise RuntimeError(
            "Phase 1 planning did not return the required structured build_spec output."
        )

    dispatcher.partial_build_spec = scene_plan_output.build_spec.model_dump()
    dispatcher.partial_target_duration_seconds = planning_options.max_turns
    dispatcher.partial_plan_text = plan_text
    dispatcher._print("  [PLAN] Visible scene plan accepted.")
    dispatcher._print("  [PROGRESS] Phase 2/5: implementation pass")
    if planning_options.allowed_tools:
        dispatcher._print(f"  [SYS] Allowed tools: {', '.join(planning_options.allowed_tools)}")

    emit_status(
        event_callback,
        task_status="running",
        phase="scene",
        message="Visible scene plan accepted. Beginning implementation pass.",
    )

    return planning_result_summary or {}


async def run_phase2_implementation(
    implementation_prompt: str,
    build_options_instance: Any,
    dispatcher: _MessageDispatcher,
    event_callback: Callable[[PipelineEvent], None] | None,
    cli_stderr_lines: list[str],
) -> dict[str, Any]:
    """Execute Phase 2: implementation pass."""
    async for message in query(prompt=implementation_prompt, options=build_options_instance):
        dispatcher.dispatch(message)
        if dispatcher.implementation_started:
            if not has_visible_scene_plan(dispatcher.collected_text):
                dispatcher._print("")
                dispatcher._print("[ERR] Blocking implementation before visible scene plan.")
                if dispatcher.implementation_start_reason:
                    dispatcher._print(
                        f"  First implementation step: {dispatcher.implementation_start_reason}"
                    )
                dispatcher._print(
                    "  Emit the required planning scaffold before writing scene.py, "
                    "editing Python files, or running Manim."
                )
                raise RuntimeError(
                    "Claude began implementation before emitting the required "
                    "visible scene-plan pass"
                )

    return dispatcher.result_summary or {}
