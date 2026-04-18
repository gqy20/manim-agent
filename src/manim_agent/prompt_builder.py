"""Prompt building helpers for the staged Manim pipeline."""

from __future__ import annotations

import json


def format_target_duration(seconds: int) -> str:
    """Format a target runtime for prompt guidance."""
    if seconds < 60:
        return f"{seconds} seconds"
    minutes, remainder = divmod(seconds, 60)
    if remainder == 0:
        return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"
    return f"{minutes}m {remainder}s"


def build_user_prompt(
    user_text: str,
    target_duration_seconds: int,
    *,
    include_intro_outro: bool = False,
) -> str:
    """Legacy single-pass execution guidance."""
    normalized = user_text.strip()
    target_duration = format_target_duration(target_duration_seconds)
    guidance = (
        "\n\nExecution requirements:\n"
        f"- Target final video duration: about {target_duration}.\n"
        "- Design the beat count, pacing, and narration density to land close to that target runtime.\n"
        "- Prefer shorter, more focused explanations for 30-second and 1-minute runs, and more developed walkthroughs for 3-minute and 5-minute runs.\n"
        "- Use the runtime-injected `manim-production` plugin.\n"
        "- The plugin location is a read-only runtime reference, not the writable task directory.\n"
        "- Do not use Bash, Read, ls, find, or path probes to verify whether the plugin exists.\n"
        "- Use the `scene-plan`, `scene-build`, `scene-direction`, `layout-safety`, `narration-sync`, and `render-review` skills directly through the injected plugin workflow.\n"
        "- Treat `layout-safety` as an advisory audit for crowded beats, not as a blind auto-fail rule.\n"
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
    if include_intro_outro:
        guidance += (
            "\n- Use the `intro-outro` skill to design branded intro and/or outro segments.\n"
            "- Emit `intro_spec` and/or `outro_spec` in structured_output if appropriate for this content.\n"
            "- If you generate intro or outro video files, report their paths as `intro_video_path` and `outro_video_path`.\n"
            "- Keep intro and outro segments between 3–5 seconds each.\n"
        )
    return f"{normalized}{guidance}" if normalized else guidance.strip()


def build_scene_plan_prompt(
    user_text: str,
    target_duration_seconds: int,
    *,
    include_intro_outro: bool = False,
) -> str:
    """Build a planning-only prompt that must stop after the visible plan."""
    normalized = user_text.strip()
    target_duration = format_target_duration(target_duration_seconds)
    guidance = (
        "\n\nPlanning pass only:\n"
        f"- Target final video duration: about {target_duration}.\n"
        "- Use the runtime-injected `scene-plan` skill and stop after producing the visible plan.\n"
        "- The plugin location is a read-only runtime reference, not the writable task directory.\n"
        "- Do not use Bash, Read, ls, find, or path probes to verify plugin files in this pass.\n"
        "- Do not write, edit, or render any code in this pass.\n"
        "- Use only lightweight reference reads if needed.\n"
        "- Return a Markdown plan with these exact section headings: `Mode`, `Learning Goal`, `Audience`, `Beat List`, `Narration Outline`, `Visual Risks`, and `Build Handoff`.\n"
        "- Keep the plan compact and implementation-ready.\n"
    )
    if include_intro_outro:
        guidance += (
            "- If appropriate for this content, include an `Intro / Outro Planning` section "
            "in the plan that specifies desired intro/outro styles, durations, and key text.\n"
        )
    return f"{normalized}{guidance}" if normalized else guidance.strip()


def build_implementation_prompt(
    user_text: str,
    target_duration_seconds: int,
    plan_text: str,
    *,
    include_intro_outro: bool = False,
) -> str:
    """Build the implementation prompt after a planning pass has been accepted."""
    normalized = user_text.strip()
    target_duration = format_target_duration(target_duration_seconds)
    guidance = (
        "\n\nImplementation pass:\n"
        f"- Target final video duration: about {target_duration}.\n"
        "- The visible scene plan below is approved. Implement from it instead of creating a new plan.\n"
        "- Continue using the runtime-injected `manim-production` plugin.\n"
        "- Use `scene-build`, `scene-direction`, `layout-safety`, `narration-sync`, and `render-review` through that injected plugin workflow.\n"
        "- Use `layout-safety` as an advisory audit for dense beats and interpret warnings with visual judgment.\n"
        "- The plugin location is a read-only runtime reference, not the writable task directory.\n"
        "- Do not use shell or filesystem probes to verify plugin files during implementation.\n"
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
    )
    if include_intro_outro:
        guidance += (
            "- If the approved plan includes an Intro / Outro Planning section, "
            "use the `intro-outro` skill to implement those segments.\n"
            "- Emit `intro_spec`/`outro_spec` and `intro_video_path`/`outro_video_path` in structured_output if applicable.\n"
            "- Render intro/outro scenes using Manim fallback (TitleCard/EndingCard) or Revideo as appropriate.\n"
        )
    guidance += (
        "\nApproved visible scene plan:\n"
        f"{plan_text}\n"
    )
    return f"{normalized}{guidance}" if normalized else guidance.strip()


def build_output_repair_prompt(
    user_text: str,
    target_duration_seconds: int,
    *,
    plan_text: str,
    partial_output: dict[str, object] | None,
    video_output: str | None,
    segment_video_paths: list[str] | None = None,
    render_mode: str = "full",
) -> str:
    """Build a no-tools repair prompt for missing structured output fields."""
    normalized = user_text.strip()
    target_duration = format_target_duration(target_duration_seconds)
    render_mode = render_mode.strip().lower() or "full"
    segment_video_paths = [path for path in (segment_video_paths or []) if path]
    partial_output_json = json.dumps(
        partial_output or {},
        ensure_ascii=False,
        indent=2,
    )
    render_artifact_guidance = (
        f"- Keep `video_output` set to `{video_output}`.\n"
        "- Preserve the existing render artifact path exactly as-is.\n"
    )
    if render_mode == "segments" and not video_output:
        render_artifact_guidance = (
            "- Keep `video_output` as null. Do not invent a synthetic full-length render path.\n"
            "- Preserve `segment_video_paths` as the ordered beat-level deliverables.\n"
        )
        if segment_video_paths:
            segment_paths_json = json.dumps(segment_video_paths, ensure_ascii=False, indent=2)
            render_artifact_guidance += (
                "- Keep `segment_video_paths` exactly aligned to these existing files:\n"
                f"{segment_paths_json}\n"
            )
    guidance = (
        "\n\nStructured output repair pass:\n"
        f"- Target final video duration: about {target_duration}.\n"
        "- Do not use any tools in this pass.\n"
        "- Do not write, edit, render, probe, or inspect files.\n"
        "- The render already exists and should be preserved.\n"
        "- Your only job is to return a corrected structured_output object.\n"
        f"- `render_mode` remains `{render_mode}`.\n"
        f"{render_artifact_guidance}"
        "- Fill in the missing build bookkeeping from the approved plan and the work you already completed.\n"
        "- `implemented_beats` must be the ordered beat titles actually implemented.\n"
        "- `build_summary` must briefly summarize what the animation build accomplished.\n"
        "- `deviations_from_plan` must be an array, even if empty.\n"
        "- `beat_to_narration_map` must contain one short narration mapping line per beat in order.\n"
        "- `narration_coverage_complete` must be true only if the narration would cover the full beat flow.\n"
        "- `estimated_narration_duration_seconds` must be a reasonable estimate.\n"
        "- If source code was not captured, leave `source_code` as null instead of inventing it.\n"
        "- If audio/subtitle artifacts do not exist yet, keep them null.\n"
        "- Return only the corrected structured output via the schema.\n"
        "\nApproved visible scene plan:\n"
        f"{plan_text}\n"
        "\nCurrent partial structured output:\n"
        f"{partial_output_json}\n"
    )
    return f"{normalized}{guidance}" if normalized else guidance.strip()


def build_narration_generation_prompt(
    user_text: str,
    target_duration_seconds: int,
    *,
    plan_text: str,
    implemented_beats: list[str],
    beat_to_narration_map: list[str],
    build_summary: str | None,
    video_duration_seconds: float | None,
) -> str:
    """Build a no-tools prompt for generating natural spoken Chinese narration.

    Runs after the render is complete, so the LLM has full context about
    what was actually built vs what was planned.
    """
    normalized = user_text.strip()
    target_duration = format_target_duration(target_duration_seconds)

    beats_json = json.dumps(implemented_beats, ensure_ascii=False, indent=2)
    beat_map_json = json.dumps(beat_to_narration_map, ensure_ascii=False, indent=2)

    duration_context = (
        f"{video_duration_seconds:.1f}s"
        if video_duration_seconds is not None and video_duration_seconds > 0
        else "unknown"
    )

    # Character count targets based on video duration
    effective_duration = video_duration_seconds or target_duration_seconds
    char_min = max(20, int(effective_duration * 2.5))
    char_max = max(40, int(effective_duration * 4))

    guidance = (
        "\n\nNarration generation pass:\n"
        "- Do not use any tools in this pass.\n"
        "- Do not write, edit, render, probe, or inspect files.\n"
        "- Your ONLY job is to produce a natural, spoken Simplified Chinese narration "
        "for the completed educational math animation.\n\n"

        "## What you are narrating\n"
        f"- Original user request: {normalized}\n"
        f"- Target video duration: about {target_duration}\n"
        f"- Actual rendered video duration: {duration_context}\n\n"

        "## Animation structure (what was actually built)\n"
        f"- Implemented beats (in order):\n{beats_json}\n\n"
        f"- Beat-to-narration hints from the build phase:\n{beat_map_json}\n\n"
        f"- Build summary: {build_summary or '(none)'}\n\n"

        "## Approved scene plan (reference for context)\n"
        f"{plan_text}\n\n"

        "## Output requirements\n"
        "- Write the narration as continuous spoken Chinese, like a teacher explaining to students.\n"
        "- Each sentence should map naturally to one animation beat in order.\n"
        "- Use conversational connectors: '首先', '接下来', '然后', "
        "'我们可以看到', '注意', '最后', '也就是说'.\n"
        "- Avoid bullet points, numbered lists, or instructional language.\n"
        "- Do NOT include the user request text, topic title only, or meta-instructions.\n"
        "- Do NOT say '请制作', '演示', '生成', or any task-description phrasing.\n"
        "- Do NOT read formulas verbatim — describe what they show instead.\n"
        f"- Match the narration length to the video duration: aim for about "
        f"{char_min}–{char_max} Chinese characters.\n"
        "- Return ONLY the narration text as your response, nothing else.\n"
    )
    return f"{normalized}{guidance}" if normalized else guidance.strip()
