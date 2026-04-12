"""Planning/build/review gate helpers for the Manim pipeline."""

from __future__ import annotations

import re

from .output_schema import PipelineOutput

PLAN_SECTION_HEADINGS = (
    "Mode",
    "Learning Goal",
    "Audience",
    "Beat List",
    "Narration Outline",
    "Visual Risks",
    "Build Handoff",
)
PLAN_SKILL_SIGNATURE = "mp-scene-plan-v1"


def estimate_spoken_duration_seconds(text: str) -> float:
    """Roughly estimate spoken duration for mixed Chinese/Latin narration."""
    normalized = text.strip()
    if not normalized:
        return 0.0

    cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", normalized))
    latin_words = len(re.findall(r"[A-Za-z0-9]+", normalized))
    punctuation = len(re.findall(r"[锛屻€傦紒锛?.!?锛?锛?銆乚", normalized))

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


def has_visible_scene_plan(collected_text: list[str]) -> bool:
    """Check whether the assistant emitted the required planning scaffold."""
    if not collected_text:
        return False

    text = "\n".join(collected_text)
    matches = 0
    for heading in PLAN_SECTION_HEADINGS:
        if re.search(
            rf"(?im)^\s*(?:#+\s*|\d+\.\s*)?{re.escape(heading)}\s*:?\s*$",
            text,
        ):
            matches += 1
    return matches >= len(PLAN_SECTION_HEADINGS)


def has_scene_plan_skill_signature(collected_text: list[str]) -> bool:
    """Check whether the visible plan includes the scene-plan skill canary."""
    if not collected_text:
        return False

    text = "\n".join(collected_text)
    return bool(
        re.search(
            rf"(?im)^\s*Skill Signature\s*:\s*{re.escape(PLAN_SKILL_SIGNATURE)}\s*$",
            text,
        )
    )


def extract_visible_scene_plan_text(collected_text: list[str], max_chars: int = 6000) -> str:
    """Return a bounded slice of assistant text for downstream review context."""
    text = "\n".join(part.strip() for part in collected_text if part and part.strip()).strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


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
