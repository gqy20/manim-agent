"""FFmpeg helpers for muxing rendered Manim video with TTS audio."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path


DEFAULT_SUBTITLE_STYLE: dict[str, str] = {
    "FontSize": "20",
    "PrimaryColour": "&H00FFFFFF",
    "OutlineColour": "&H00000000",
    "Outline": "2",
    "BorderStyle": "3",
    "MarginV": "20",
}

_DURATION_TOLERANCE = 0.05


def _validate_inputs(video_path: str, audio_path: str, output_path: str) -> None:
    """Validate that input files exist before invoking FFmpeg."""
    if not Path(video_path).exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    if not Path(audio_path).exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")


async def _get_duration(file_path: str) -> float:
    """Return media duration in seconds using ffprobe."""
    proc = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        file_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {file_path}: {stderr.decode().strip()}")

    data = json.loads(stdout.decode())
    return float(data["format"]["duration"])


def _align_durations(video_duration: float, audio_duration: float) -> str:
    """Choose a duration-alignment strategy for FFmpeg."""
    if video_duration <= 0 or audio_duration <= 0:
        return "shortest"

    if video_duration == audio_duration:
        return "shortest"

    diff_ratio = abs(video_duration - audio_duration) / max(video_duration, audio_duration)

    if diff_ratio < _DURATION_TOLERANCE:
        return "speed"
    if video_duration > audio_duration:
        return "pad_audio"
    return "tpad"


def _build_ffmpeg_cmd(
    video_path: str,
    audio_path: str,
    subtitle_path: str | None,
    output_path: str,
    align_strategy: str,
    video_duration: float,
    audio_duration: float,
    subtitle_style: dict[str, str] | None = None,
) -> list[str]:
    """Build the FFmpeg command for the chosen alignment strategy."""
    style = subtitle_style or DEFAULT_SUBTITLE_STYLE
    cmd = ["ffmpeg", "-y", "-i", video_path, "-i", audio_path]

    video_filters: list[str] = []
    if align_strategy == "tpad" and audio_duration > video_duration:
        pad_seconds = audio_duration - video_duration
        video_filters.append(f"tpad=stop_mode=clone:stop_duration={pad_seconds:.3f}")

    if subtitle_path:
        style_str = ",".join(f"{key}={value}" for key, value in style.items())
        video_filters.append(f"subtitles={subtitle_path}:force_style='{style_str}'")

    if video_filters:
        cmd.extend(["-vf", ",".join(video_filters)])

    cmd.extend(["-map", "0:v", "-map", "1:a"])
    cmd.extend(["-c:v", "libx264" if video_filters else "copy", "-c:a", "aac"])

    if align_strategy in {"shortest", "speed"}:
        cmd.append("-shortest")
    elif align_strategy == "pad_audio":
        # Keep the full rendered animation and fill the audio tail with silence.
        cmd.extend(["-af", "apad", "-t", f"{video_duration:.3f}"])
    elif align_strategy == "tpad":
        cmd.append("-shortest")

    cmd.append(output_path)
    return cmd


async def build_final_video(
    video_path: str,
    audio_path: str,
    subtitle_path: str | None,
    output_path: str,
    subtitle_style: dict[str, str] | None = None,
) -> str:
    """Mux the rendered video, TTS audio, and optional subtitles into a final MP4."""
    _validate_inputs(video_path, audio_path, output_path)

    video_dur = await _get_duration(video_path)
    audio_dur = await _get_duration(audio_path)
    strategy = _align_durations(video_dur, audio_dur)

    cmd = _build_ffmpeg_cmd(
        video_path,
        audio_path,
        subtitle_path,
        output_path,
        strategy,
        video_dur,
        audio_dur,
        subtitle_style,
    )

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed (exit code {proc.returncode}): {stderr.decode().strip()}")

    return output_path
