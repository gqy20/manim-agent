"""Timeline helpers for beat-driven audio orchestration."""

from __future__ import annotations

import json
from pathlib import Path

from .beat_schema import BeatSpec, TimelineSpec


def finalize_timeline(beats: list[BeatSpec]) -> TimelineSpec:
    """Assign start/end offsets to beats using measured audio durations."""
    cursor = 0.0
    normalized: list[BeatSpec] = []
    for beat in beats:
        duration = float(beat.actual_audio_duration_seconds or 0.0)
        beat.start_seconds = cursor
        beat.end_seconds = cursor + duration
        cursor += duration
        normalized.append(beat)
    return TimelineSpec(beats=normalized, total_duration_seconds=cursor)


def write_timeline_file(timeline: TimelineSpec, output_path: str) -> str:
    """Persist a resolved timeline as JSON."""
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(timeline.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(target)
