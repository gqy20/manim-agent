"""Phase 3 (render resolve + review), Phase 4 (TTS), and Phase 5 (mux) pipeline functions."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from claude_agent_sdk import ResultMessage, query

from .audio_orchestrator import orchestrate_audio_assets
from .dispatcher import _EMOJI, _MessageDispatcher
from .pipeline_config import build_options, emit_status
from .pipeline_events import PipelineEvent
from .pipeline_gates import (
    duration_target_issue,
    has_narration_sync_summary,
    has_structured_build_summary,
    merge_result_summaries,
    narration_is_too_short_for_video,
)
from .prompt_builder import format_target_duration
from .render_review import extract_review_frames
from .schemas import Phase3RenderReviewOutput, PhaseSchemaRegistry
from .segment_renderer import (
    build_segment_render_plan,
    discover_segment_video_paths,
    extract_video_segments,
    read_segment_render_plan,
    write_segment_render_plan,
)
from .video_builder import _get_duration, build_final_video, concat_videos

logger = logging.getLogger(__name__)


def _require_real_segment_outputs(*, po: Any, render_mode: str) -> None:
    """Fail fast when segment mode lacks real segment render artifacts."""
    if po is None or render_mode != "segments":
        return

    segment_video_paths = [
        str(path) for path in (getattr(po, "segment_video_paths", None) or []) if path
    ]
    if segment_video_paths and all(Path(path).exists() for path in segment_video_paths):
        return

    raise RuntimeError(
        "High-quality segment render outputs are required in segments mode. "
        "No real segment render outputs were produced."
    )


def _require_structured_build_bookkeeping(po: Any) -> None:
    """Fail fast when the implementation pass skipped required bookkeeping."""
    if has_structured_build_summary(po) and has_narration_sync_summary(po):
        return

    raise RuntimeError(
        "Structured build bookkeeping is required. "
        "Missing implemented beat bookkeeping, build summary, or narration sync metadata."
    )


def _collect_known_artifacts(*, resolved_cwd: str, dispatcher: _MessageDispatcher) -> list[str]:
    """Collect concrete task artifacts to use as repair evidence, not as truth source."""
    output_dir = Path(resolved_cwd)
    patterns = ("*.mp4", "*.mp3", "*.wav", "*.srt", "*.json", "*.py")
    artifacts: set[str] = set()
    for pattern in patterns:
        for path in output_dir.rglob(pattern):
            if path.is_file():
                artifacts.add(str(path.resolve()))
    if dispatcher.task_notification_output_file:
        artifacts.add(str(Path(dispatcher.task_notification_output_file).resolve()))
    return sorted(artifacts)


def _phase3_gate_issue(*, po: Any, render_mode: str, resolved_cwd: str) -> str | None:
    """Return the first blocking issue for Phase 3 delivery stability."""
    if po is None:
        return "missing structured pipeline output"

    if not getattr(po, "implemented_beats", None):
        return "implemented_beats is empty"
    if not getattr(po, "build_summary", None):
        return "build_summary is missing"

    normalized_mode = render_mode.strip().lower() or "full"
    if normalized_mode == "segments":
        segment_video_paths = [
            str(path) for path in (getattr(po, "segment_video_paths", None) or []) if path
        ]
        if not segment_video_paths:
            return "segment_video_paths is empty"
        for raw_path in segment_video_paths:
            path = Path(raw_path)
            if not path.is_absolute():
                path = Path(resolved_cwd) / raw_path
            if not path.exists():
                return f"segment video does not exist: {raw_path}"
        if getattr(po, "segment_render_complete", None) is not True:
            return "segment_render_complete is not true"
        return None

    video_output = getattr(po, "video_output", None)
    if not video_output:
        return "video_output is missing"
    video_path = Path(video_output)
    if not video_path.is_absolute():
        video_path = Path(resolved_cwd) / video_output
    if not video_path.exists():
        return f"video_output does not exist: {video_output}"
    return None


# ── Frame labeling ──────────────────────────────────────────────────


def _build_frame_labels(
    implemented_beats: list[str] | None,
    count: int,
) -> list[str]:
    """Generate beat-aligned labels for extracted review frames."""
    if count <= 0 or not implemented_beats:
        return [f"frame_{i + 1}" for i in range(count)]

    labels: list[str] = ["opening"]
    n_beats = len(implemented_beats)

    if count > 2:
        middle_slots = count - 2
        for i in range(middle_slots):
            beat_idx = min(i, n_beats - 1)
            beat_name = implemented_beats[beat_idx].replace(" ", "_")
            labels.append(f"beat_{beat_idx + 1}__{beat_name}")

    if count >= 2:
        last_beat = implemented_beats[-1].replace(" ", "_")
        labels.append(f"ending__{last_beat}")

    while len(labels) < count:
        labels.append(f"frame_{len(labels) + 1}")
    return labels[:count]


# ── Render Review ──────────────────────────────────────────────────


async def run_render_review(
    *,
    user_text: str,
    plan_text: str,
    video_output: str,
    frame_paths: list[str],
    target_duration_seconds: int,
    actual_duration_seconds: float | None,
    cwd: str,
    system_prompt: str,
    quality: str,
    log_callback: Callable[[str], None] | None,
    implemented_beats: list[str] | None = None,
) -> Phase3RenderReviewOutput:
    """Ask Claude to review sampled render frames and return a structured verdict."""
    beat_labels = _build_frame_labels(implemented_beats, len(frame_paths))
    labeled_frames = "\n".join(
        f"- Frame {i + 1} [{label}]: {path}"
        for i, (path, label) in enumerate(zip(frame_paths, beat_labels))
    )
    measured_duration = (
        f"{actual_duration_seconds:.2f}s"
        if actual_duration_seconds is not None and actual_duration_seconds > 0
        else "unknown"
    )
    review_prompt = (
        "Use the `render-review` skill to review this rendered Manim video.\n"
        "Do not write, edit, or render anything in this pass. Only review the output.\n\n"
        "## MANDATORY: Visual Analysis of Each Frame\n"
        "You MUST use the Read tool to examine EVERY frame image file listed below.\n"
        "For each frame, provide a visual assessment covering:\n"
        "- What is visibly on screen (objects, text, formulas, labels, arrows)\n"
        "- Visual density (sparse / balanced / crowded)\n"
        "- Whether the focal point is clear and unambiguous\n"
        "- Label and formula readability (clear / partially obscured / illegible)\n"
        "- Any visual issues (overlap, cutoff, too small, wrong position, etc.)\n\n"
        f"Original user request:\n{user_text}\n\n"
        "Duration target:\n"
        f"- requested runtime: about {format_target_duration(target_duration_seconds)}\n"
        f"- measured render runtime: {measured_duration}\n\n"
        "Approved build plan/context:\n"
        f"{plan_text or '(no plan text available)'}\n\n"
        f"Rendered video path:\n- {video_output}\n\n"
        "Sampled review frames (MUST read each one):\n"
        f"{labeled_frames}\n"
    )

    review_opts = build_options(
        cwd=cwd,
        system_prompt=system_prompt,
        max_turns=16,
        quality=quality,
        log_callback=log_callback,
        output_format=PhaseSchemaRegistry.output_format_schema("phase3_render_review"),
        allowed_tools=["Read", "Glob", "Grep"],
    )

    result_message: ResultMessage | None = None
    async for message in query(prompt=review_prompt, options=review_opts):
        pass

    if result_message is None or result_message.structured_output is None:
        raise RuntimeError("Render review did not produce a structured verdict.")

    raw = result_message.structured_output
    if isinstance(raw, str):
        raw = json.loads(raw)
    return Phase3RenderReviewOutput.model_validate(raw)


# ── Phase 3: Render Resolve + Review ───────────────────────────────


async def run_phase3_render(
    *,
    dispatcher: _MessageDispatcher,
    hook_state: Any,
    user_text: str,
    plan_text: str,
    result_summary: dict[str, Any] | None,
    target_duration_seconds: int,
    resolved_cwd: str,
    system_prompt: str,
    quality: str,
    prompt_file: str | None,
    log_callback: Callable[[str], None] | None,
    event_callback: Callable[[PipelineEvent], None] | None,
    cli_stderr_lines: list[str],
    render_mode: str = "full",
) -> tuple[Any, str | None, list[str]]:
    """Execute Phase 3: resolve render output, optional repair, frame review.

    Returns (po, video_output, review_frames).
    """
    from . import prompt_builder

    dispatcher._print(f"  {_EMOJI['gear']} Phase 3/5: resolve render output")
    logger.debug(
        "run_pipeline: phase2: dispatcher.video_output before extraction = %r",
        dispatcher.video_output,
    )
    logger.debug(
        "run_pipeline: phase2: hook captured source code keys = %s",
        list(hook_state.captured_source_code.keys()),
    )

    po = dispatcher.get_pipeline_output()
    logger.debug("run_pipeline: PipelineOutput after get_pipeline_output: %r", po)
    video_output = po.video_output if po else None
    render_mode = render_mode.strip().lower() or "full"

    render_status_message = (
        "Resolving render output (pipeline_result -> structured output -> task_notification -> "
        "filesystem scan)"
    )
    if dispatcher.task_notification_status in {"failed", "stopped"}:
        note = (
            f"Task ended with status={dispatcher.task_notification_status} "
            f"before/while resolving output"
        )
        if dispatcher.task_notification_summary:
            note = f"{note}: {dispatcher.task_notification_summary}"
        render_status_message = note
    elif video_output:
        render_status_message = "Render output resolved. Proceeding according to pipeline mode."

    emit_status(
        event_callback,
        task_status="running",
        phase="render",
        message=render_status_message,
    )
    logger.debug("run_pipeline: video_output = %r", video_output)

    if po is not None:
        po.render_mode = render_mode
        po.segment_render_complete = bool(
            render_mode == "segments"
            and getattr(po, "segment_video_paths", None)
            and all(Path(path).exists() for path in getattr(po, "segment_video_paths", []))
        )
        _populate_po_metadata(po, dispatcher, result_summary, target_duration_seconds, plan_text)
        existing_segments = discover_segment_video_paths(
            output_dir=resolved_cwd,
            expected_paths=getattr(po, "segment_video_paths", None),
        )
        if existing_segments:
            po.segment_video_paths = existing_segments
            po.segment_render_complete = render_mode == "segments"
            dispatcher._print(
                f"  [RENDER] Discovered pre-rendered segment videos: {len(existing_segments)}"
            )
        segment_visual_track = await _resolve_segment_review_video(
            po=po,
            render_mode=render_mode,
            output_dir=resolved_cwd,
        )
        if segment_visual_track is not None:
            video_output = segment_visual_track
            po.video_output = segment_visual_track
            render_status_message = (
                "Render output resolved from beat segment videos. Proceeding in segment mode."
            )
            emit_status(
                event_callback,
                task_status="running",
                phase="render",
                message=render_status_message,
            )

    segment_paths_for_repair = (
        [str(path) for path in (getattr(po, "segment_video_paths", None) or []) if path]
        if po is not None
        else []
    )
    has_segment_render_artifacts = bool(
        render_mode == "segments"
        and segment_paths_for_repair
        and all(Path(path).exists() for path in segment_paths_for_repair)
    )
    gate_issue = _phase3_gate_issue(po=po, render_mode=render_mode, resolved_cwd=resolved_cwd)
    if (video_output or has_segment_render_artifacts or dispatcher.raw_result_text) and gate_issue:
        dispatcher._print(
            "  [REPAIR] Structured output is incomplete. Running a no-tools repair pass."
        )
        repair_visual_reference = video_output
        try:
            partial_output = dispatcher.get_persistable_pipeline_output()
        except AttributeError:
            if po is not None and hasattr(po, "__dict__"):
                partial_output = dict(vars(po))
            else:
                partial_output = None
        repair_prompt = prompt_builder.build_output_repair_prompt(
            user_text,
            target_duration_seconds,
            plan_text=plan_text,
            partial_output=partial_output,
            raw_result_text=dispatcher.raw_result_text,
            video_output=None if render_mode == "segments" else repair_visual_reference,
            segment_video_paths=segment_paths_for_repair,
            artifact_inventory=_collect_known_artifacts(
                resolved_cwd=resolved_cwd,
                dispatcher=dispatcher,
            ),
            validation_issue=gate_issue,
            render_mode=render_mode,
        )
        repair_opts = build_options(
            cwd=resolved_cwd,
            system_prompt=system_prompt,
            max_turns=6,
            prompt_file=prompt_file,
            quality=quality,
            log_callback=log_callback,
            allowed_tools=[],
        )
        async for message in query(prompt=repair_prompt, options=repair_opts):
            dispatcher.dispatch(message)

        repair_result_summary = dispatcher.result_summary
        result_summary = merge_result_summaries(result_summary, repair_result_summary)
        po = dispatcher.get_pipeline_output()
        if po is not None:
            _populate_po_metadata(
                po, dispatcher, result_summary, target_duration_seconds, plan_text
            )
            if (
                render_mode == "segments"
                and not getattr(po, "video_output", None)
                and repair_visual_reference
            ):
                po.video_output = repair_visual_reference
                video_output = repair_visual_reference
        gate_issue = _phase3_gate_issue(po=po, render_mode=render_mode, resolved_cwd=resolved_cwd)

    if gate_issue is None and has_structured_build_summary(po) and has_narration_sync_summary(po):
        pass

    if po is not None and video_output and po.duration_seconds is None:
        try:
            po.duration_seconds = await _get_duration(video_output)
        except Exception as exc:
            logger.debug(
                "run_pipeline: unable to probe render duration for %r: %s", video_output, exc
            )

    _require_real_segment_outputs(po=po, render_mode=render_mode)

    if gate_issue is not None:
        dispatcher._print("")
        dispatcher._print(f"{_EMOJI['cross']} Claude did not produce a valid pipeline output.")
        dispatcher._print(f"  Blocking issue: {gate_issue}")
        if dispatcher.task_notification_status:
            dispatcher._print(f"  Task notification status: {dispatcher.task_notification_status}")
        if dispatcher.task_notification_summary:
            dispatcher._print(f"  Notification summary: {dispatcher.task_notification_summary}")
        if dispatcher.task_notification_output_file:
            dispatcher._print(
                f"  Notification output_file: {dispatcher.task_notification_output_file}"
            )
        if dispatcher.result_summary:
            s = dispatcher.result_summary
            if s.get("is_error"):
                dispatcher._print(f"  SDK result flagged error: stop_reason={s.get('stop_reason')}")
        if dispatcher.task_notification_status == "stopped":
            dispatcher._print("  Note: task status is 'stopped', so render was interrupted.")
        elif dispatcher.task_notification_status == "failed":
            dispatcher._print("  Note: task status is 'failed', so render likely did not finish.")
        if dispatcher.result_summary:
            s = dispatcher.result_summary
            dispatcher._print(f"  Turns: {s.get('turns', '?')} | Error: {s.get('is_error', '?')}")
        collected = "\n".join(dispatcher.collected_text)
        if collected.strip():
            dispatcher._print("  --- Agent text output (first 2000 chars) ---")
            dispatcher._print(collected[:2000])
            if len(collected) > 2000:
                dispatcher._print(f"  ... ({len(collected)} chars total)")
            dispatcher._print("  --- Output end ---")
        else:
            dispatcher._print("  (Agent produced no text output)")
        failure_phase = dispatcher.task_notification_status or "unknown"
        raise RuntimeError(
            "Claude did not produce a valid pipeline output. "
            f"Phase 3/5 outcome status={failure_phase}. "
            f"Blocking issue: {gate_issue}."
        )

    # Render review + duration check
    dispatcher._print("  [REVIEW] Sampling render frames for quality review")
    emit_status(
        event_callback,
        task_status="running",
        phase="render",
        message="Reviewing sampled frames before final success",
    )
    review_frames = await extract_review_frames(
        video_output,
        resolved_cwd,
        implemented_beats=po.implemented_beats if po else None,
    )
    review_result: Phase3RenderReviewOutput | None = None
    review_warning: str | None = None
    try:
        review_result = await run_render_review(
            user_text=user_text,
            plan_text=plan_text,
            video_output=video_output,
            frame_paths=review_frames,
            target_duration_seconds=target_duration_seconds,
            actual_duration_seconds=po.duration_seconds if po is not None else None,
            cwd=resolved_cwd,
            system_prompt=system_prompt,
            quality=quality,
            log_callback=log_callback,
            implemented_beats=po.implemented_beats if po is not None else None,
        )
    except RuntimeError as exc:
        if "structured verdict" not in str(exc):
            raise
        review_warning = (
            "Render review did not produce a structured verdict. "
            "Continuing because review formatting can be incomplete without blocking delivery."
        )
        dispatcher._print(f"  [WARN] {review_warning}")
        logger.warning("run_pipeline: %s", review_warning)

    if review_result is not None:
        dispatcher._print(f"  [REVIEW] {review_result.summary}")
        if review_result.blocking_issues:
            for issue in review_result.blocking_issues:
                dispatcher._print(f"  [REVIEW][BLOCK] {issue}")
        if review_result.suggested_edits:
            for edit in review_result.suggested_edits:
                dispatcher._print(f"  [REVIEW][FIX] {edit}")
        if po is not None:
            po.review_summary = review_result.summary
            po.review_approved = review_result.approved
            po.review_blocking_issues = list(review_result.blocking_issues)
            po.review_suggested_edits = list(review_result.suggested_edits)
            po.review_frame_paths = list(review_frames)
            po.review_frame_analyses = [
                fa.model_dump() for fa in (review_result.frame_analyses or [])
            ]
            po.review_vision_analysis_used = review_result.vision_analysis_used
        dispatcher.partial_review_summary = review_result.summary
        dispatcher.partial_review_approved = review_result.approved
        dispatcher.partial_review_blocking_issues = list(review_result.blocking_issues)
        dispatcher.partial_review_suggested_edits = list(review_result.suggested_edits)
        dispatcher.partial_review_frame_paths = list(review_frames)
        dispatcher.partial_review_frame_analyses = [
            fa.model_dump() for fa in (review_result.frame_analyses or [])
        ]
        dispatcher.partial_review_vision_analysis_used = review_result.vision_analysis_used
        if not review_result.approved:
            raise RuntimeError(
                "Rendered video failed the render-review gate. "
                + "; ".join(review_result.blocking_issues or [review_result.summary])
            )
    else:
        if po is not None:
            po.review_summary = review_warning
            po.review_approved = None
            po.review_blocking_issues = []
            po.review_suggested_edits = []
            po.review_frame_paths = list(review_frames)
        dispatcher.partial_review_summary = review_warning
        dispatcher.partial_review_approved = None
        dispatcher.partial_review_blocking_issues = []
        dispatcher.partial_review_suggested_edits = []
        dispatcher.partial_review_frame_paths = list(review_frames)

    duration_issue = duration_target_issue(
        po.duration_seconds if po is not None else None,
        target_duration_seconds,
        formatter=format_target_duration,
    )
    if duration_issue is not None:
        dispatcher._print(f"  [WARN] {duration_issue}")
        logger.warning("run_pipeline: duration target miss: %s", duration_issue)
    if duration_issue is None and po is not None and po.duration_seconds is not None:
        dispatcher._print(
            "  [REVIEW] Duration check passed: "
            f"{po.duration_seconds:.1f}s vs target {target_duration_seconds}s"
        )

    return po, video_output, review_frames


async def _resolve_segment_review_video(
    *,
    po: Any,
    render_mode: str,
    output_dir: str,
) -> str | None:
    """Build a temporary reviewable video when segment mode has no full render."""
    if po is None or render_mode != "segments":
        return None
    if getattr(po, "video_output", None):
        return None

    segment_video_paths = [
        str(path) for path in (getattr(po, "segment_video_paths", None) or []) if path
    ]
    if not segment_video_paths:
        return None
    if not all(Path(path).exists() for path in segment_video_paths):
        return None

    review_track_path = str(Path(output_dir) / "review_visual_track.mp4")
    logger.info(
        "run_phase3_render: composing %d segment videos into review track",
        len(segment_video_paths),
    )
    return await concat_videos(
        video_paths=segment_video_paths,
        output_path=review_track_path,
    )


# ── Phase 4: TTS Synthesis ───────────────────────────────────────


async def run_phase4_tts(
    *,
    dispatcher: _MessageDispatcher,
    narration_text: str,
    video_output: str,
    voice_id: str,
    model: str,
    output_path: str,
    po: Any,
    user_text: str,
    plan_text: str,
    target_duration_seconds: int,
    bgm_enabled: bool = False,
    bgm_prompt: str | None = None,
    preset: str = "default",
    event_callback: Callable[[PipelineEvent], None] | None,
) -> Any:
    """Execute Phase 4: beat-aware audio orchestration.

    Returns an audio orchestration result.
    """
    dispatcher._print(f"  {_EMOJI['gear']} Phase 4/5: orchestrate beat audio assets")
    emit_status(
        event_callback,
        task_status="running",
        phase="tts",
        message="Synthesizing beat narration and optional BGM",
    )
    if narration_is_too_short_for_video(
        narration_text, po.duration_seconds if po is not None else None
    ):
        warning = (
            "Narration is much shorter than the rendered video. "
            "Muxing will preserve the full animation and leave trailing silence "
            "instead of truncating it."
        )
        dispatcher._print(f"  [WARN] {warning}")
        logger.warning(
            "run_pipeline: %s video=%r narration=%r", warning, video_output, narration_text
        )
    dispatcher._print(
        f"\n{_EMOJI['tts']} Audio orchestration in progress... (voice={voice_id}, model={model})"
    )
    audio_result = await orchestrate_audio_assets(
        po=po,
        user_text=user_text,
        plan_text=plan_text,
        target_duration_seconds=target_duration_seconds,
        voice_id=voice_id,
        model=model,
        output_dir=str(Path(output_path).parent),
        bgm_enabled=bgm_enabled,
        bgm_prompt=bgm_prompt,
        preset=preset,
    )
    if po is not None:
        po.beats = [beat.model_dump() for beat in audio_result.beats]
        po.audio_segments = [
            {
                "beat_id": beat.id,
                "audio_path": beat.audio_path,
                "subtitle_path": beat.subtitle_path,
                "extra_info_path": beat.extra_info_path,
                "duration_seconds": beat.actual_audio_duration_seconds,
                "tts_mode": beat.tts_mode,
            }
            for beat in audio_result.beats
        ]
        po.timeline_path = audio_result.timeline_path
        po.timeline_total_duration_seconds = audio_result.timeline.total_duration_seconds
        po.audio_concat_path = audio_result.concatenated_audio_path
        po.audio_path = audio_result.concatenated_audio_path
        po.subtitle_path = audio_result.concatenated_subtitle_path
        po.bgm_path = audio_result.bgm_path
        po.bgm_duration_ms = audio_result.bgm_duration_ms
        po.bgm_prompt = audio_result.bgm_prompt
        po.bgm_volume = 0.12 if audio_result.bgm_path else None
        po.audio_mix_mode = "voice_with_bgm" if audio_result.bgm_path else "voice_only"
        po.render_mode = getattr(po, "render_mode", None) or "full"
        if audio_result.timeline.total_duration_seconds > 0:
            po.tts_duration_ms = int(audio_result.timeline.total_duration_seconds * 1000)
        existing_segment_paths = discover_segment_video_paths(
            output_dir=str(Path(output_path).parent),
            expected_paths=getattr(po, "segment_video_paths", None),
        )
        segment_plan = build_segment_render_plan(
            timeline=audio_result.timeline,
            output_dir=str(Path(output_path).parent),
            scene_file=getattr(po, "scene_file", None),
            scene_class=getattr(po, "scene_class", None),
        )
        po.segment_video_paths = existing_segment_paths or [
            segment.output_path for segment in segment_plan.segments
        ]
        po.segment_render_complete = bool(
            getattr(po, "render_mode", None) == "segments" and existing_segment_paths
        )
        po.segment_render_plan_path = write_segment_render_plan(
            segment_plan,
            str(Path(output_path).parent / "segment_render_plan.json"),
        )
    dispatcher._print(f"  [TTS] Beat segments: {len(audio_result.beats)}")
    dispatcher._print(
        f"  [TTS] Timeline duration: {audio_result.timeline.total_duration_seconds:.2f}s"
    )
    dispatcher._print(
        "  [TTS] Output mode: "
        f"{'subtitle ready' if audio_result.concatenated_subtitle_path else 'audio-only mux'}"
    )
    if audio_result.bgm_path:
        dispatcher._print(f"  [BGM] Done: path={audio_result.bgm_path}")
    return audio_result


# ── Phase 5: Mux ──────────────────────────────────────────────────


async def run_phase5_mux(
    *,
    dispatcher: _MessageDispatcher,
    video_output: str,
    audio_result: Any,
    output_path: str,
    po: Any,
    bgm_volume: float = 0.12,
    intro_outro: bool = False,
    event_callback: Callable[[PipelineEvent], None] | None,
) -> str:
    """Execute Phase 5: video mux + optional BGM + optional intro/outro.

    Returns the final video path.
    """
    mux_video_path, used_segment_visuals = await _resolve_mux_video_source(
        video_output=video_output,
        output_path=output_path,
        po=po,
    )
    dispatcher._print("[MUX] Phase 5/5: mux final video")
    mux_desc = (
        "video + narration + bgm + subtitle"
        if audio_result.bgm_path is not None
        else "video + audio + subtitle"
    )
    dispatcher._print(f"[MUX] FFmpeg in progress... ({mux_desc})")
    emit_status(
        event_callback,
        task_status="running",
        phase="mux",
        message="Muxing final video",
    )
    final_video = await build_final_video(
        video_path=mux_video_path,
        audio_path=audio_result.concatenated_audio_path,
        subtitle_path=audio_result.concatenated_subtitle_path,
        output_path=output_path,
        bgm_path=audio_result.bgm_path,
        bgm_volume=bgm_volume,
    )
    if po is not None:
        po.final_video_output = final_video
        if getattr(po, "segment_render_plan_path", None) and not used_segment_visuals:
            try:
                segment_plan = read_segment_render_plan(po.segment_render_plan_path)
                po.segment_video_paths = await extract_video_segments(final_video, segment_plan)
            except Exception as exc:
                logger.warning("run_phase5_mux: segment extraction skipped: %s", exc)

    # Optional intro/outro concat
    if intro_outro and po is not None:
        concat_parts: list[str | None] = []
        if po.intro_video_path and Path(po.intro_video_path).exists():
            concat_parts.append(po.intro_video_path)
        concat_parts.append(final_video)
        if po.outro_video_path and Path(po.outro_video_path).exists():
            concat_parts.append(po.outro_video_path)

        if len(concat_parts) > 1:
            dispatcher._print("[MUX] Phase 5b: concatenating intro/outro segments")
            emit_status(
                event_callback,
                task_status="running",
                phase="concat",
                message="Concatenating intro/outro segments",
            )
            final_video = await concat_videos(
                video_paths=cast("list[str]", concat_parts),
                output_path=output_path,
            )
            if po is not None:
                po.final_video_output = final_video
            dispatcher._print(f"[MUX] Concatenated video: {final_video}")

    dispatcher._print(f"\n{_EMOJI['check']} Video generation complete: {final_video}")
    return final_video


async def _resolve_mux_video_source(
    *,
    video_output: str,
    output_path: str,
    po: Any,
) -> tuple[str, bool]:
    """Choose the visual source for muxing.

    Prefer already-rendered beat segments when they exist on disk; otherwise
    fall back to the single full-length render output.
    """
    if po is None:
        return video_output, False

    if getattr(po, "render_mode", None) == "segments":
        segment_video_paths = [
            str(path) for path in (getattr(po, "segment_video_paths", None) or []) if path
        ]
        if not segment_video_paths or not all(Path(path).exists() for path in segment_video_paths):
            raise RuntimeError(
                "High-quality segment render outputs are required in segments mode. "
                "No real segment render outputs were produced."
            )

    segment_video_paths = [
        str(path) for path in (getattr(po, "segment_video_paths", None) or []) if path
    ]
    if not segment_video_paths:
        return video_output, False

    resolved_paths = [Path(path) for path in segment_video_paths]
    if not all(path.exists() for path in resolved_paths):
        return video_output, False

    segment_track_path = str(Path(output_path).with_name("segment_visual_track.mp4"))
    visual_track = await concat_videos(
        video_paths=segment_video_paths,
        output_path=segment_track_path,
    )
    logger.info(
        "run_phase5_mux: using %d pre-rendered segment videos as mux source",
        len(segment_video_paths),
    )
    return visual_track, True


# ── PO metadata ───────────────────────────────────────────────────


def _populate_po_metadata(
    po: Any,
    dispatcher: _MessageDispatcher,
    result_summary: dict[str, Any] | None,
    target_duration_seconds: int,
    plan_text: str,
) -> None:
    """Fill standard metadata fields on PO from dispatcher + result summary."""
    if result_summary is not None:
        po.run_turns = result_summary.get("turns")
        po.run_duration_ms = result_summary.get("duration_ms")
        po.run_cost_usd = result_summary.get("cost_usd")
    po.run_tool_use_count = dispatcher.tool_use_count
    po.run_tool_stats = dict(dispatcher.tool_stats)
    po.target_duration_seconds = target_duration_seconds
    po.plan_text = plan_text
    dispatcher.partial_render_mode = getattr(po, "render_mode", None)
    dispatcher.partial_segment_render_complete = getattr(po, "segment_render_complete", None)
    dispatcher.partial_build_summary = po.build_summary
    dispatcher.partial_deviations_from_plan = list(po.deviations_from_plan)
    dispatcher.partial_beat_to_narration_map = list(po.beat_to_narration_map)
    dispatcher.partial_narration_coverage_complete = po.narration_coverage_complete
    dispatcher.partial_estimated_narration_duration_seconds = (
        po.estimated_narration_duration_seconds
    )


# ── BGM prompt ────────────────────────────────────────────────────


def _build_default_bgm_prompt(user_text: str, preset: str, narration_text: str) -> str:
    """Build a restrained instrumental BGM prompt for narrated teaching videos."""
    preset_style = {
        "educational": "calm educational underscore, soft piano and light strings",
        "presentation": "clean modern underscore, light piano and gentle ambient textures",
        "proof": "subtle thoughtful underscore, restrained piano and low strings",
        "concept": "clear contemporary underscore, piano and marimba with light ambient texture",
        "default": "calm instrumental underscore, soft piano and light strings",
    }.get(preset, "calm instrumental underscore, soft piano and light strings")
    topic_hint = user_text.strip() or narration_text.strip() or "a narrated math explainer"
    return (
        f"{preset_style}, background music for a narrated explainer video about {topic_hint}, "
        "instrumental only, no vocals, non-distracting, low intensity, supportive, "
        "steady pacing, suitable under spoken narration"
    )
