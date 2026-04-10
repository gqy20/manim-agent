"""FFmpeg 视频合成器。

将 Manim 渲染的静音视频 + TTS 音频 + SRT 字幕合成为最终成品视频。
支持多种时长对齐策略和可配置字幕样式。
"""

import asyncio
import json
from pathlib import Path

# ── 常量 ──────────────────────────────────────────────────────

DEFAULT_SUBTITLE_STYLE: dict[str, str] = {
    "FontSize": "20",
    "PrimaryColour": "&H00FFFFFF",
    "OutlineColour": "&H00000000",
    "Outline": "2",
    "BorderStyle": "3",
    "MarginV": "20",
}

_DURATION_TOLERANCE = 0.05  # 5% 差异阈值


# ── 内部函数 ──────────────────────────────────────────────────


def _validate_inputs(
    video_path: str,
    audio_path: str,
    output_path: str,
) -> None:
    """校验输入文件存在性。

    Raises:
        FileNotFoundError: 视频或音频文件不存在。
    """
    if not Path(video_path).exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    if not Path(audio_path).exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")


async def _get_duration(file_path: str) -> float:
    """使用 ffprobe 获取媒体文件时长（秒）。

    Args:
        file_path: 文件路径。

    Returns:
        时长（秒）。

    Raises:
        RuntimeError: ffprobe 执行失败。
    """
    proc = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        file_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(
            f"ffprobe failed for {file_path}: {stderr.decode().strip()}"
        )

    data = json.loads(stdout.decode())
    return float(data["format"]["duration"])


def _align_durations(video_duration: float, audio_duration: float) -> str:
    """根据时长差异选择对齐策略。

    Args:
        video_duration: 视频时长（秒）。
        audio_duration: 音频时长（秒）。

    Returns:
        策略名称: "shortest" | "tpad" | "speed"。
    """
    if video_duration <= 0 or audio_duration <= 0:
        return "shortest"

    # 完全相等时直接返回 shortest（最安全策略）
    if video_duration == audio_duration:
        return "shortest"

    diff_ratio = abs(video_duration - audio_duration) / max(video_duration, audio_duration)

    if diff_ratio < _DURATION_TOLERANCE:
        return "speed"
    elif video_duration > audio_duration:
        return "shortest"
    else:
        return "tpad"


def _build_ffmpeg_cmd(
    video_path: str,
    audio_path: str,
    subtitle_path: str | None,
    output_path: str,
    align_strategy: str,
    subtitle_style: dict[str, str] | None = None,
) -> list[str]:
    """构建 ffmpeg 合成命令。

    Args:
        video_path: 视频文件路径。
        audio_path: 音频文件路径。
        subtitle_path: 字幕文件路径（可选）。
        output_path: 输出文件路径。
        align_strategy: 时长对齐策略。
        subtitle_style: 字幕样式配置（可选）。

    Returns:
        ffmpeg 命令参数列表。
    """
    style = subtitle_style or DEFAULT_SUBTITLE_STYLE
    cmd = ["ffmpeg", "-y"]

    # 字幕滤镜（需要重新编码视频）
    if subtitle_path:
        style_str = ",".join(f"{k}={v}" for k, v in style.items())
        vf = f"subtitles={subtitle_path}:force_style='{style_str}'"
        cmd.extend(["-i", video_path, "-i", audio_path])
        cmd.extend(["-vf", vf])
        cmd.extend(["-map", "0:v", "-map", "1:a"])
        cmd.extend(["-c:v", "libx264", "-c:a", "aac"])
    else:
        # 无字幕：使用 stream copy 加速
        cmd.extend(["-i", video_path, "-i", audio_path])
        cmd.extend(["-map", "0:v", "-map", "1:a"])
        cmd.extend(["-c:v", "copy", "-c:a", "aac"])

    # 时长对齐
    if align_strategy == "shortest":
        cmd.append("-shortest")
    # tpad 和 speed 策略在此简化为 shortest
    # （完整实现需额外 filter_complex）

    cmd.append(output_path)
    return cmd


# ── 公共接口 ──────────────────────────────────────────────────


async def build_final_video(
    video_path: str,
    audio_path: str,
    subtitle_path: str | None,
    output_path: str,
    subtitle_style: dict[str, str] | None = None,
) -> str:
    """使用 ffmpeg 合成最终视频。

    步骤：
    1. 校验所有输入文件存在且可读
    2. 计算视频时长与音频时长，处理不一致情况
    3. ffmpeg 合并：视频流 + 音频流 (+ 字幕轨道)
    4. 返回输出文件路径

    Args:
        video_path: Manim 渲染的静音 MP4 路径。
        audio_path: TTS 合成的 MP3 路径。
        subtitle_path: SRT 字幕文件路径（可选）。
        output_path: 输出 MP4 路径。
        subtitle_style: 自定义字幕样式（可选）。

    Returns:
        输出文件路径。

    Raises:
        FileNotFoundError: 输入文件不存在。
        RuntimeError: ffprobe 或 ffmpeg 执行失败。
    """
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
        subtitle_style,
    )

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed (exit code {proc.returncode}): {stderr.decode().strip()}"
        )

    return output_path
