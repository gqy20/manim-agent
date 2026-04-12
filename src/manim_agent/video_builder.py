"""FFmpeg helpers for muxing rendered Manim video with narration and optional BGM."""

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


def _validate_inputs(
    video_path: str,
    audio_path: str,
    output_path: str,
    bgm_path: str | None = None,
) -> None:
    """Validate that input files exist before invoking FFmpeg."""
    if not Path(video_path).exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    if not Path(audio_path).exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    if bgm_path and not Path(bgm_path).exists():
        raise FileNotFoundError(f"BGM file not found: {bgm_path}")


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
    bgm_path: str | None = None,
    bgm_volume: float = 0.12,
) -> list[str]:
    """Build the FFmpeg command for the chosen alignment strategy."""
    style = subtitle_style or DEFAULT_SUBTITLE_STYLE
    cmd = ["ffmpeg", "-y", "-i", video_path, "-i", audio_path]
    has_bgm = bool(bgm_path)
    if has_bgm:
        cmd.extend(["-stream_loop", "-1", "-i", bgm_path])

    video_filters: list[str] = []
    if align_strategy == "tpad" and audio_duration > video_duration:
        pad_seconds = audio_duration - video_duration
        video_filters.append(f"tpad=stop_mode=clone:stop_duration={pad_seconds:.3f}")

    if subtitle_path:
        style_str = ",".join(f"{key}={value}" for key, value in style.items())
        video_filters.append(f"subtitles={subtitle_path}:force_style='{style_str}'")

    if video_filters:
        cmd.extend(["-vf", ",".join(video_filters)])

    if has_bgm:
        safe_bgm_volume = min(max(bgm_volume, 0.0), 1.0)
        cmd.extend(
            [
                "-filter_complex",
                (
                    f"[2:a]volume={safe_bgm_volume:.3f}[bgm];"
                    "[1:a][bgm]amix=inputs=2:duration=longest:normalize=0[mix]"
                ),
                "-map",
                "0:v",
                "-map",
                "[mix]",
            ]
        )
    else:
        cmd.extend(["-map", "0:v", "-map", "1:a"])
    cmd.extend(["-c:v", "libx264" if video_filters else "copy", "-c:a", "aac"])

    if has_bgm:
        cmd.append("-shortest")
    elif align_strategy in {"shortest", "speed"}:
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
    bgm_path: str | None = None,
    bgm_volume: float = 0.12,
) -> str:
    """Mux the rendered video, TTS audio, and optional subtitles into a final MP4."""
    _validate_inputs(video_path, audio_path, output_path, bgm_path)

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
        bgm_path,
        bgm_volume,
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


async def concat_videos(
    video_paths: list[str],
    output_path: str,
) -> str:
    """Concatenate multiple MP4 videos in order using FFmpeg concat demuxer.

    Uses stream copy (-c copy) so no re-encoding occurs — this is fast
    and preserves original quality.  All input videos must share the same
    resolution, framerate, and codec.

    Args:
        video_paths: Ordered list of MP4 file paths
                    (e.g. [intro.mp4, main.mp4, outro.mp4]).
                    None / empty values are silently skipped.
        output_path: Destination path for the concatenated output.

    Returns:
        The output_path on success.

    Raises:
        FileNotFoundError: If any specified video file does not exist.
        RuntimeError: If FFmpeg concat fails or no valid inputs remain.
    """
    import tempfile

    # Filter out None/empty and validate existence
    valid_paths: list[str] = []
    for p in video_paths:
        if not p:
            continue
        if not Path(p).exists():
            raise FileNotFoundError(f"Video file not found: {p}")
        valid_paths.append(p)

    if len(valid_paths) < 2:
        # Nothing to concatenate — copy single input to output if needed
        if len(valid_paths) == 1 and valid_paths[0] != output_path:
            import shutil

            shutil.copy2(valid_paths[0], output_path)
        return output_path

    # Write concat list file (required by FFmpeg concat demuxer)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as list_file:
        for p in valid_paths:
            # Escape single-quotes for safe 0 protocol handling
            safe = p.replace("'", "'\\''")
            list_file.write(f"file '{safe}'\n")
        list_path = list_file.name

    try:
        cmd = [
            "ffmpeg",
            "-y",                           # Overwrite output
            "-f", "concat",                  # Concat demuxer format
            "-safe", "0",                   # Allow unsafe paths (needed for absolute)
            "-i", list_path,                # Input list file
            "-c", "copy",                   # Stream copy — no re-encoding
            output_path,
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(
                f"ffmpeg concat failed (exit code {proc.returncode}): {stderr.decode().strip()}"
            )
    finally:
        # Clean up temp list file
        Path(list_path).unlink(missing_ok=True)

    return output_path
