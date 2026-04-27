"""Subtitle helpers for beat-normalized narration timelines."""

from __future__ import annotations

import re
from pathlib import Path

from .beat_schema import TimelineSpec


def write_timeline_srt(timeline: TimelineSpec, output_path: str) -> str | None:
    """Write an SRT file whose cues are aligned to the resolved beat timeline."""
    cues: list[tuple[float, float, str]] = []
    for beat in timeline.beats:
        text = (beat.narration_text or beat.narration_hint or beat.title).strip()
        start = float(beat.start_seconds or 0.0)
        end = float(beat.end_seconds or start)
        if not text or end <= start:
            continue
        cues.extend(_split_beat_into_cues(text, start, end))

    if not cues:
        return None

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for index, (start, end, text) in enumerate(cues, start=1):
        lines.extend(
            [
                str(index),
                f"{_format_srt_timestamp(start)} --> {_format_srt_timestamp(end)}",
                text,
                "",
            ]
        )
    target.write_text("\n".join(lines), encoding="utf-8")
    return str(target)


def _split_beat_into_cues(text: str, start: float, end: float) -> list[tuple[float, float, str]]:
    chunks = _split_text(text)
    if not chunks:
        return []
    duration = max(0.0, end - start)
    if duration <= 0:
        return []

    cue_duration = duration / len(chunks)
    cues: list[tuple[float, float, str]] = []
    cursor = start
    for index, chunk in enumerate(chunks):
        cue_start = cursor
        cue_end = end if index == len(chunks) - 1 else min(end, cursor + cue_duration)
        if cue_end > cue_start:
            cues.append((cue_start, cue_end, chunk))
        cursor = cue_end
    return cues


def _split_text(text: str, max_chars: int = 32) -> list[str]:
    parts = [
        part.strip()
        for part in re.split(r"(?<=[。！？!?；;，,])", text.replace("\n", " "))
        if part.strip()
    ]
    chunks: list[str] = []
    for part in parts or [text.strip()]:
        if len(part) <= max_chars:
            chunks.append(part)
            continue
        for index in range(0, len(part), max_chars):
            chunk = part[index : index + max_chars].strip()
            if chunk:
                chunks.append(chunk)
    return chunks


def _format_srt_timestamp(seconds: float) -> str:
    milliseconds = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
