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
from .prompt_debug import update_prompt_artifact, write_prompt_artifact
from .render_review import extract_review_frames
from .schemas import Phase3RenderReviewOutput, PhaseSchemaRegistry
from .segment_renderer import (
    build_segment_render_plan,
    discover_segment_video_paths,
    extract_video_segments,
    read_segment_render_plan,
    write_segment_render_plan,
)
from .token_pricing import estimate_result_cost_cny
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
    return_summary: bool = False,
) -> Phase3RenderReviewOutput | tuple[Phase3RenderReviewOutput, dict[str, Any]]:
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
        "Only review the existing render. Do not write, edit, or render anything.\n"
        "Read every sampled frame listed below before returning the structured verdict.\n\n"
        f"Original user request:\n{user_text}\n\n"
        "Duration target:\n"
        f"- requested runtime: about {format_target_duration(target_duration_seconds)}\n"
        f"- measured render runtime: {measured_duration}\n\n"
        "Approved build context:\n"
        f"{plan_text or '(no plan text available)'}\n\n"
        "Implemented beats:\n"
        f"{', '.join(implemented_beats or []) or '(not provided)'}\n\n"
        f"Rendered video path:\n- {video_output}\n\n"
        "Sampled review frames:\n"
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
    write_prompt_artifact(
        output_dir=cwd,
        phase_id="phase3",
        phase_name="Render Review",
        system_prompt=system_prompt,
        user_prompt=review_prompt,
        inputs={
            "user_text": user_text,
            "target_duration_seconds": target_duration_seconds,
            "video_output": video_output,
            "frame_paths": frame_paths,
            "implemented_beats": implemented_beats or [],
            "actual_duration_seconds": actual_duration_seconds,
        },
        options=review_opts,
        options_summary={"output_schema": "phase3_render_review"},
        referenced_artifacts={"video_output": video_output},
    )

    result_message: ResultMessage | None = None
    async for message in query(prompt=review_prompt, options=review_opts):
        if isinstance(message, ResultMessage):
            result_message = message

    if result_message is None or result_message.structured_output is None:
        raise RuntimeError("Render review did not produce a structured verdict.")

    raw = result_message.structured_output
    if isinstance(raw, str):
        raw = json.loads(raw)
    result_summary = _result_message_summary(result_message)
    output = Phase3RenderReviewOutput.model_validate(raw)
    update_prompt_artifact(
        output_dir=cwd,
        phase_id="phase3",
        output_snapshot={
            "review_output": output.model_dump(),
            "result_summary": result_summary,
        },
    )
    if return_summary:
        return output, result_summary
    return output


def _result_message_summary(
    result_message: ResultMessage,
    model_name: str | None = None,
) -> dict[str, Any]:
    cost_estimate = estimate_result_cost_cny(
        model_name,
        result_message.usage,
        result_message.model_usage,
    )
    return {
        "turns": result_message.num_turns,
        "cost_usd": result_message.total_cost_usd,
        "cost_cny": cost_estimate.get("estimated_cost_cny"),
        "pricing_model": cost_estimate.get("pricing_model"),
        "input_tokens": cost_estimate.get("input_tokens"),
        "output_tokens": cost_estimate.get("output_tokens"),
        "cache_read_tokens": cost_estimate.get("cache_read_tokens"),
        "cache_write_tokens": cost_estimate.get("cache_write_tokens"),
        "total_tokens": cost_estimate.get("total_tokens"),
        "duration_ms": result_message.duration_ms,
        "is_error": result_message.is_error,
        "stop_reason": result_message.stop_reason,
        "errors": result_message.errors,
    }


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
    no_render_review: bool = False,
) -> tuple[Any, str | None, list[str]]:
    """Execute Phase 3: resolve render output and optional frame review.

    When *no_render_review* is True, skip the AI visual review pass and
    set placeholder review fields so the pipeline can continue to Phase 3.5+.

    Returns (po, video_output, review_frames).
    """
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
    review_frames: list[str] = []

    if no_render_review:
        skipped_msg = "Render review skipped (no_render_review=True). Accepting Phase 2B output."
        dispatcher._print(f"  [SKIP] {skipped_msg}")
        emit_status(
            event_callback,
            task_status="running",
            phase="render",
            message=skipped_msg,
        )
        if po is not None:
            po.review_summary = skipped_msg
            po.review_approved = True
            po.review_blocking_issues = []
            po.review_suggested_edits = []
            po.review_frame_paths = []
            po.review_frame_analyses = []
            po.review_vision_analysis_used = False
        dispatcher.partial_review_summary = skipped_msg
        dispatcher.partial_review_approved = True
        dispatcher.partial_review_blocking_issues = []
        dispatcher.partial_review_suggested_edits = []
        dispatcher.partial_review_frame_paths = []
        dispatcher.partial_review_frame_analyses = []
        dispatcher.partial_review_vision_analysis_used = False
    else:
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
            review_subdir="phase3_review_frames",
        )
        review_result: Phase3RenderReviewOutput | None = None
        review_warning: str | None = None
        try:
            review_response = await run_render_review(
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
                return_summary=True,
            )
            if isinstance(review_response, tuple):
                review_result, review_result_summary = review_response
            else:
                review_result = review_response
                review_result_summary = None

            if review_result_summary is not None:
                result_summary = merge_result_summaries(result_summary, review_result_summary)
                dispatcher.partial_run_turns = (
                    result_summary.get("turns") if result_summary else None
                )
                dispatcher.partial_run_duration_ms = (
                    result_summary.get("duration_ms") if result_summary else None
                )
                dispatcher.partial_run_cost_usd = (
                    result_summary.get("cost_usd") if result_summary else None
                )
                dispatcher.partial_run_cost_cny = (
                    result_summary.get("cost_cny") if result_summary else None
                )
                dispatcher.partial_run_model_name = (
                    result_summary.get("model_name") if result_summary else None
                )
                dispatcher.partial_run_pricing_model = (
                    result_summary.get("pricing_model") if result_summary else None
                )
                dispatcher.partial_render_review_result_summary = review_result_summary
                if po is not None:
                    po.run_turns = result_summary.get("turns") if result_summary else None
                    po.run_duration_ms = (
                        result_summary.get("duration_ms") if result_summary else None
                    )
                    po.run_cost_usd = result_summary.get("cost_usd") if result_summary else None
                    po.run_cost_cny = result_summary.get("cost_cny") if result_summary else None
                    po.run_model_name = (
                        result_summary.get("model_name") if result_summary else None
                    )
                    po.run_pricing_model = (
                        result_summary.get("pricing_model") if result_summary else None
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
    write_prompt_artifact(
        output_dir=str(Path(output_path).parent),
        phase_id="phase4",
        phase_name="Audio Orchestration",
        inputs={
            "voice_id": voice_id,
            "model": model,
            "target_duration_seconds": target_duration_seconds,
            "bgm_enabled": bgm_enabled,
            "bgm_prompt": bgm_prompt,
            "preset": preset,
            "narration_text": narration_text,
            "implemented_beats": list(getattr(po, "implemented_beats", []) or []),
            "beat_to_narration_map": list(getattr(po, "beat_to_narration_map", []) or []),
        },
        referenced_artifacts={
            "video_output": video_output,
            "timeline": "timeline.json",
            "audio_manifest": "audio_manifest.json",
        },
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
    update_prompt_artifact(
        output_dir=str(Path(output_path).parent),
        phase_id="phase4",
        output_snapshot={
            "beats": [beat.model_dump() for beat in audio_result.beats],
            "timeline_path": audio_result.timeline_path,
            "timeline_total_duration_seconds": audio_result.timeline.total_duration_seconds,
            "audio_concat_path": audio_result.concatenated_audio_path,
            "subtitle_path": audio_result.concatenated_subtitle_path,
            "bgm_path": audio_result.bgm_path,
            "bgm_duration_ms": audio_result.bgm_duration_ms,
            "audio_mix_mode": getattr(po, "audio_mix_mode", None) if po is not None else None,
        },
    )
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
    write_prompt_artifact(
        output_dir=str(Path(output_path).parent),
        phase_id="phase5",
        phase_name="Mux",
        inputs={
            "video_output": video_output,
            "mux_video_path": mux_video_path,
            "output_path": output_path,
            "audio_path": getattr(audio_result, "concatenated_audio_path", None),
            "subtitle_path": getattr(audio_result, "concatenated_subtitle_path", None),
            "bgm_path": getattr(audio_result, "bgm_path", None),
            "bgm_volume": bgm_volume,
            "intro_outro": intro_outro,
            "used_segment_visuals": used_segment_visuals,
        },
        referenced_artifacts={
            "segment_render_plan": getattr(po, "segment_render_plan_path", None)
            if po is not None
            else None,
        },
    )
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
    update_prompt_artifact(
        output_dir=str(Path(output_path).parent),
        phase_id="phase5",
        output_snapshot={
            "final_video_output": final_video,
            "used_segment_visuals": used_segment_visuals,
            "segment_video_paths": list(getattr(po, "segment_video_paths", []) or [])
            if po is not None
            else [],
        },
    )
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
        po.run_cost_cny = result_summary.get("cost_cny")
        po.run_model_name = result_summary.get("model_name")
        po.run_pricing_model = result_summary.get("pricing_model")
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
