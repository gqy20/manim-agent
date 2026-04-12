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


async def extract_review_frames(video_path: str, output_dir: str) -> list[str]:
    """Extract a few PNG frames for visual review."""
    video = Path(video_path)
    review_dir = Path(output_dir) / "review_frames"
    review_dir.mkdir(parents=True, exist_ok=True)

    duration_seconds = await _get_duration(str(video))
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
