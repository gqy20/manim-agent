"""Helpers for extracting review frames from rendered videos."""

from __future__ import annotations

import asyncio
from pathlib import Path

from .video_builder import _get_duration


def _build_review_timestamps(duration_seconds: float) -> list[float]:
    """Choose a few representative timestamps for a quick visual review."""
    if duration_seconds <= 0:
        return [0.0]

    if duration_seconds < 4:
        candidates = [0.0, duration_seconds * 0.5, max(duration_seconds - 0.1, 0.0)]
    else:
        candidates = [
            min(0.5, duration_seconds),
            duration_seconds * 0.2,
            duration_seconds * 0.55,
            max(duration_seconds - 0.75, 0.0),
        ]

    unique: list[float] = []
    for ts in sorted(candidates):
        rounded = round(max(ts, 0.0), 2)
        if rounded not in unique:
            unique.append(rounded)
    return unique


def build_beat_aligned_timestamps(
    duration_seconds: float,
    implemented_beats: list[str] | None = None,
    max_frames: int = 6,
) -> list[float]:
    """Compute frame extraction timestamps aligned to beat boundaries.

    When *implemented_beats* is provided, extracts one frame per beat midpoint
    plus opening and ending frames.  Falls back to ``_build_review_timestamps``
    when no beat data is available.
    """
    if not implemented_beats or duration_seconds <= 0:
        return _build_review_timestamps(duration_seconds)

    n_beats = len(implemented_beats)
    target = min(n_beats + 2, max_frames)
    candidates: list[float] = []

    # Opening frame
    candidates.append(min(0.5, duration_seconds * 0.05))

    # Distribute middle frames across beats
    usable_start = 1.0
    usable_end = max(duration_seconds - 1.0, usable_start + 1.0)
    usable_span = usable_end - usable_start

    if n_beats > 0 and target > 2:
        middle_count = target - 2
        for i in range(middle_count):
            # Map i onto beat indices (round-robin if more slots than beats)
            beat_frac = (i + 0.5) / middle_count
            ts = usable_start + beat_frac * usable_span
            candidates.append(ts)

    # Ending frame
    candidates.append(max(duration_seconds - 0.75, 0.0))

    # Deduplicate & clamp
    unique: list[float] = []
    for ts in sorted(candidates):
        rounded = round(max(ts, 0.0), 2)
        if rounded not in unique and rounded <= duration_seconds:
            unique.append(rounded)
    return unique


async def extract_review_frames(
    video_path: str,
    output_dir: str,
    implemented_beats: list[str] | None = None,
) -> list[str]:
    """Extract a few PNG frames for visual review.

    When *implemented_beats* is provided, timestamps are aligned to beat
    boundaries for more representative sampling.
    """
    video = Path(video_path)
    review_dir = Path(output_dir) / "review_frames"
    review_dir.mkdir(parents=True, exist_ok=True)

    duration_seconds = await _get_duration(str(video))
    if implemented_beats:
        timestamps = build_beat_aligned_timestamps(
            duration_seconds, implemented_beats
        )
    else:
        timestamps = _build_review_timestamps(duration_seconds)
    frame_paths: list[str] = []

    for index, timestamp in enumerate(timestamps, start=1):
        frame_path = review_dir / f"frame_{index:02d}.png"
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",
            "-ss",
            f"{timestamp:.2f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            str(frame_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(
                f"ffmpeg frame extraction failed at {timestamp:.2f}s: {stderr.decode().strip()}"
            )
        frame_paths.append(str(frame_path))

    return frame_paths
