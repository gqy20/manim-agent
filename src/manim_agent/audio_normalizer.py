"""FFmpeg helpers for fitting beat audio into fixed visual time windows."""

from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AudioNormalizationResult:
    output_path: str
    duration_seconds: float
    strategy: str


async def normalize_audio_to_duration(
    *,
    audio_path: str,
    output_path: str,
    target_duration_seconds: float,
    actual_duration_seconds: float | None = None,
    min_speed: float = 0.85,
    max_speed: float = 1.2,
) -> AudioNormalizationResult:
    """Create an audio file whose duration fits a fixed beat window.

    The visual beat duration is treated as authoritative. Short audio is padded
    with silence; moderately long audio is sped up; very long audio is sped up
    to the configured maximum and trimmed as a last-resort delivery fallback.
    """
    source = Path(audio_path).resolve()
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    if source.stat().st_size <= 0:
        raise RuntimeError(f"Audio file is empty: {source}")

    target = Path(output_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    target_duration = max(0.0, float(target_duration_seconds or 0.0))
    actual_duration = max(0.0, float(actual_duration_seconds or 0.0))

    if target_duration <= 0 or actual_duration <= 0:
        if source != target:
            shutil.copy2(source, target)
        return AudioNormalizationResult(
            output_path=str(target),
            duration_seconds=actual_duration,
            strategy="copy_no_target",
        )

    ratio = actual_duration / target_duration
    if 0.98 <= ratio <= 1.02:
        if source != target:
            shutil.copy2(source, target)
        return AudioNormalizationResult(
            output_path=str(target),
            duration_seconds=actual_duration,
            strategy="copy_within_tolerance",
        )

    if ratio < 0.98:
        await _run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source),
                "-af",
                "apad",
                "-t",
                f"{target_duration:.3f}",
                str(target),
            ]
        )
        return AudioNormalizationResult(
            output_path=str(target),
            duration_seconds=target_duration,
            strategy="pad_silence",
        )

    speed = min(max(ratio, min_speed), max_speed)
    filters = [f"atempo={speed:.6f}"]
    await _run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-filter:a",
            ",".join(filters),
            "-t",
            f"{target_duration:.3f}",
            str(target),
        ]
    )
    strategy = "speed_up" if ratio <= max_speed else "speed_up_and_trim"
    return AudioNormalizationResult(
        output_path=str(target),
        duration_seconds=target_duration,
        strategy=strategy,
    )


async def _run_ffmpeg(cmd: list[str]) -> None:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg audio normalization failed: {stderr.decode().strip()}")
