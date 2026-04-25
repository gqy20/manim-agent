"""Planning/build/review gate helpers for the Manim pipeline."""

from __future__ import annotations

import re
from pathlib import Path

from .schemas import BuildSpec, PipelineOutput
from .segment_renderer import discover_segment_video_paths


def estimate_spoken_duration_seconds(text: str) -> float:
    """Roughly estimate spoken duration for mixed Chinese/Latin narration."""
    normalized = text.strip()
    if not normalized:
        return 0.0

    cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", normalized))
    latin_words = len(re.findall(r"[A-Za-z0-9]+", normalized))
    punctuation = len(re.findall(r"[，。！？、；：……\.\!\?\,\;]", normalized))

    return (cjk_chars / 3.8) + (latin_words / 2.5) + (punctuation * 0.12)


def merge_result_summaries(*summaries: dict | None) -> dict | None:
    """Combine phase summaries into one aggregate summary."""
    usable = [summary for summary in summaries if summary]
    if not usable:
        return None

    merged: dict = {
        "turns": 0,
        "cost_usd": 0.0,
        "duration_ms": 0,
        "is_error": False,
        "stop_reason": None,
        "errors": [],
    }
    saw_cost = False
    for summary in usable:
        turns = summary.get("turns")
        if isinstance(turns, int):
            merged["turns"] += turns
        duration_ms = summary.get("duration_ms")
        if isinstance(duration_ms, int):
            merged["duration_ms"] += duration_ms
        cost_usd = summary.get("cost_usd")
        if isinstance(cost_usd, (int, float)):
            merged["cost_usd"] += float(cost_usd)
            saw_cost = True
        merged["is_error"] = merged["is_error"] or bool(summary.get("is_error"))
        merged["stop_reason"] = summary.get("stop_reason") or merged["stop_reason"]
        errors = summary.get("errors") or []
        if isinstance(errors, list):
            merged["errors"].extend(errors)
    if not saw_cost:
        merged["cost_usd"] = None
    return merged


def narration_is_too_short_for_video(narration: str, video_duration: float | None) -> bool:
    """Heuristic used to warn when narration is likely much shorter than the render."""
    if not narration.strip() or video_duration is None or video_duration <= 0:
        return False
    estimated = estimate_spoken_duration_seconds(narration)
    return estimated < max(4.0, video_duration * 0.45)


def allowed_duration_deviation_seconds(target_duration_seconds: int) -> float:
    """Return the acceptable runtime deviation for a requested target duration."""
    return min(45.0, max(8.0, target_duration_seconds * 0.2))


def duration_target_issue(
    actual_duration_seconds: float | None,
    target_duration_seconds: int,
    *,
    formatter,
) -> str | None:
    """Return a blocking duration issue message when render length misses the target badly."""
    if actual_duration_seconds is None or actual_duration_seconds <= 0:
        return None

    allowed_deviation = allowed_duration_deviation_seconds(target_duration_seconds)
    deviation = abs(actual_duration_seconds - target_duration_seconds)
    if deviation <= allowed_deviation:
        return None

    target_label = formatter(target_duration_seconds)
    actual_label = formatter(round(actual_duration_seconds))
    return (
        f"Rendered duration {actual_duration_seconds:.1f}s ({actual_label}) is too far from "
        f"the requested target of {target_duration_seconds}s ({target_label}). "
        f"Allowed deviation is {allowed_deviation:.1f}s."
    )


def build_fallback_narration(user_text: str) -> str:
    """Build a minimal narration fallback when structured narration is missing."""
    cleaned = " ".join(user_text.split()).strip()
    if cleaned:
        return cleaned
    return "下面我们来看这个动画的主要内容。"


def has_structured_build_summary(po: PipelineOutput | None) -> bool:
    """Require explicit build-phase bookkeeping in structured output."""
    if po is None:
        return False
    if not po.build_summary or not po.build_summary.strip():
        return False
    return len(po.implemented_beats) > 0


def has_narration_sync_summary(po: PipelineOutput | None) -> bool:
    """Require explicit narration coverage metadata in structured output."""
    if po is None:
        return False
    if len(po.beat_to_narration_map) == 0:
        return False
    if po.narration_coverage_complete is not True:
        return False
    return po.estimated_narration_duration_seconds is not None


def implementation_contract_issue(
    po: PipelineOutput | None,
    *,
    render_mode: str,
    cwd: str,
) -> str | None:
    """Return the first blocking issue in the Phase 2 implementation contract."""
    if po is None:
        return "Phase 2 produced no structured output."

    if len(po.implemented_beats) == 0:
        return "implemented_beats is empty."
    if not po.build_summary or not po.build_summary.strip():
        return "build_summary is missing."
    narration = getattr(po, "narration", None)
    if not narration or not narration.strip():
        return "narration is missing."
    if len(po.beat_to_narration_map) == 0:
        return "beat_to_narration_map is empty."
    if po.narration_coverage_complete is not True:
        return "narration_coverage_complete is not true."
    if po.estimated_narration_duration_seconds is None:
        return "estimated_narration_duration_seconds is missing."

    normalized_mode = (render_mode or "full").strip().lower() or "full"
    if normalized_mode == "segments":
        segment_paths = [
            Path(path) if Path(path).is_absolute() else Path(cwd) / path
            for path in (po.segment_video_paths or [])
            if path
        ]
        if not segment_paths:
            return "segment_video_paths is empty."
        if po.segment_render_complete is not True:
            return "segment_render_complete is not true."
        if not all(path.exists() for path in segment_paths):
            return "segment_video_paths does not point to real files."
    else:
        if not po.video_output:
            return "video_output is missing."
        video_path = Path(po.video_output)
        if not video_path.is_absolute():
            video_path = Path(cwd) / po.video_output
        if not video_path.exists():
            return "video_output does not point to a real file."

    return None


def apply_phase2_build_spec_defaults(
    po: PipelineOutput | None,
    *,
    build_spec: dict | BuildSpec | None,
    cwd: str,
    render_mode: str,
    discover_segments: bool = True,
) -> PipelineOutput | None:
    """Backfill deterministic Phase 2 fields from BuildSpec and real artifacts.

    This deliberately does not invent agent-owned fields such as
    `implemented_beats` or `build_summary`. It only fills fields that are pure
    projections of the approved build spec or the filesystem.
    """
    if po is None or build_spec is None:
        return po

    spec = build_spec if isinstance(build_spec, BuildSpec) else BuildSpec.model_validate(build_spec)
    ordered_beats = list(spec.beats)

    if not po.beats:
        po.beats = [
            {
                "id": beat.id,
                "title": beat.title,
                "narration_hint": beat.narration_intent,
                "target_duration_seconds": beat.target_duration_seconds,
                "required_elements": list(beat.required_elements),
                "segment_required": beat.segment_required,
            }
            for beat in ordered_beats
        ]

    if not po.beat_to_narration_map:
        po.beat_to_narration_map = [
            f"{beat.title} -> {beat.narration_intent}" for beat in ordered_beats
        ]

    if po.narration_coverage_complete is None:
        po.narration_coverage_complete = (
            len(po.beat_to_narration_map) == len(ordered_beats) and len(ordered_beats) > 0
        )

    if po.estimated_narration_duration_seconds is None:
        po.estimated_narration_duration_seconds = sum(
            beat.target_duration_seconds for beat in ordered_beats
        )

    normalized_mode = (render_mode or po.render_mode or "full").strip().lower() or "full"
    if normalized_mode == "segments" and discover_segments:
        expected_paths = [
            str((Path(cwd) / "segments" / f"{beat.id}.mp4").resolve())
            for beat in ordered_beats
            if beat.segment_required
        ]
        discovered_segments = discover_segment_video_paths(
            output_dir=cwd,
            expected_paths=po.segment_video_paths or expected_paths,
        )
        if discovered_segments:
            po.segment_video_paths = discovered_segments
            if po.segment_render_complete is None and len(discovered_segments) == len(
                expected_paths
            ):
                po.segment_render_complete = True

    return po
