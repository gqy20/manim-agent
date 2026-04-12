"""Prompt building helpers for the staged Manim pipeline."""

from __future__ import annotations


def format_target_duration(seconds: int) -> str:
    """Format a target runtime for prompt guidance."""
    if seconds < 60:
        return f"{seconds} seconds"
    minutes, remainder = divmod(seconds, 60)
    if remainder == 0:
        return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"
    return f"{minutes}m {remainder}s"


def build_user_prompt(user_text: str, target_duration_seconds: int) -> str:
    """Legacy single-pass execution guidance."""
    normalized = user_text.strip()
    target_duration = format_target_duration(target_duration_seconds)
    guidance = (
        "\n\nExecution requirements:\n"
        f"- Target final video duration: about {target_duration}.\n"
        "- Design the beat count, pacing, and narration density to land close to that target runtime.\n"
        "- Prefer shorter, more focused explanations for 30-second and 1-minute runs, and more developed walkthroughs for 3-minute and 5-minute runs.\n"
        "- Use the `manim-production` skills for planning, build, direction, narration, and review.\n"
        "- Start every task with a visible `scene-plan` pass before coding the scene.\n"
        "- The planning pass must be shown in Markdown with these section headings: `Mode`, `Learning Goal`, `Audience`, `Beat List`, `Narration Outline`, `Visual Risks`, and `Build Handoff`.\n"
        "- After the plan exists, implement the animation while keeping the planned beat order unless debugging requires a very small fix.\n"
        "- Do not begin writing `scene.py` until the visible planning pass is complete.\n"
        "- In structured_output, include `implemented_beats` as the ordered beat titles that were actually built.\n"
        "- In structured_output, include `build_summary` as a short summary of what the build phase implemented.\n"
        "- In structured_output, include `deviations_from_plan` as an array, even if it is empty.\n"
        "- In structured_output, include `beat_to_narration_map` with one short narration mapping line per beat.\n"
        "- In structured_output, include `narration_coverage_complete` and `estimated_narration_duration_seconds`.\n"
        "- Keep every file inside the task directory only.\n"
        "- Write the main script to scene.py unless multiple files are truly necessary.\n"
        "- Use GeneratedScene as the main Manim Scene class unless the user explicitly asks otherwise.\n"
        "- Run Manim directly from the task directory with `manim ... scene.py GeneratedScene`.\n"
        "- Do not use absolute repository paths, do not cd to the repo root, and do not invoke `.venv/Scripts/python` directly.\n"
        "- Return structured_output.narration as natural Simplified Chinese unless the user explicitly requests another language.\n"
        "- Make the narration spoken and synchronized with the animation, and cover the full flow rather than collapsing into a one-sentence summary.\n"
    )
    return f"{normalized}{guidance}" if normalized else guidance.strip()


def build_scene_plan_prompt(
    user_text: str,
    target_duration_seconds: int,
    *,
    plan_skill_signature: str,
) -> str:
    """Build a planning-only prompt that must stop after the visible plan."""
    normalized = user_text.strip()
    target_duration = format_target_duration(target_duration_seconds)
    guidance = (
        "\n\nPlanning pass only:\n"
        f"- Target final video duration: about {target_duration}.\n"
        "- Use the `scene-plan` skill and stop after producing the visible plan.\n"
        "- Do not write, edit, or render any code in this pass.\n"
        "- Use only lightweight reference reads if needed.\n"
        "- Return a Markdown plan with these exact section headings: `Mode`, `Learning Goal`, `Audience`, `Beat List`, `Narration Outline`, `Visual Risks`, and `Build Handoff`.\n"
        f"- Include the exact line `Skill Signature: {plan_skill_signature}` inside `Build Handoff`.\n"
        "- Keep the plan compact and implementation-ready.\n"
    )
    return f"{normalized}{guidance}" if normalized else guidance.strip()


def build_implementation_prompt(
    user_text: str,
    target_duration_seconds: int,
    plan_text: str,
) -> str:
    """Build the implementation prompt after a planning pass has been accepted."""
    normalized = user_text.strip()
    target_duration = format_target_duration(target_duration_seconds)
    guidance = (
        "\n\nImplementation pass:\n"
        f"- Target final video duration: about {target_duration}.\n"
        "- The visible scene plan below is approved. Implement from it instead of creating a new plan.\n"
        "- Use the `scene-build`, `scene-direction`, `narration-sync`, and `render-review` skills during their respective phases.\n"
        "- Preserve the planned beat order unless debugging requires a very small fix.\n"
        "- Do not begin with a fresh planning pass; begin implementation from the approved plan.\n"
        "- In structured_output, include `implemented_beats` as the ordered beat titles that were actually built.\n"
        "- In structured_output, include `build_summary` as a short summary of what the build phase implemented.\n"
        "- In structured_output, include `deviations_from_plan` as an array, even if it is empty.\n"
        "- In structured_output, include `beat_to_narration_map` with one short narration mapping line per beat.\n"
        "- In structured_output, include `narration_coverage_complete` and `estimated_narration_duration_seconds`.\n"
        "- Keep every file inside the task directory only.\n"
        "- Write the main script to scene.py unless multiple files are truly necessary.\n"
        "- Use GeneratedScene as the main Manim Scene class unless the user explicitly asks otherwise.\n"
        "- Run Manim directly from the task directory with `manim ... scene.py GeneratedScene`.\n"
        "- Do not use absolute repository paths, do not cd to the repo root, and do not invoke `.venv/Scripts/python` directly.\n"
        "- Return structured_output.narration as natural Simplified Chinese unless the user explicitly requests another language.\n"
        "- Make the narration spoken and synchronized with the animation, and cover the full flow rather than collapsing into a one-sentence summary.\n"
        "\nApproved visible scene plan:\n"
        f"{plan_text}\n"
    )
    return f"{normalized}{guidance}" if normalized else guidance.strip()
