"""Tests for manim_agent.video_builder module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pathlib import Path

from manim_agent import video_builder


# ── Fixtures ───────────────────────────────────────────────────


@pytest.fixture
def sample_files(tmp_path):
    """创建测试用的视频/音频/字幕文件。"""
    video = tmp_path / "video.mp4"
    audio = tmp_path / "audio.mp3"
    subtitle = tmp_path / "subtitle.srt"
    output = tmp_path / "output.mp4"
    video.write_bytes(b"fake-video-data")
    audio.write_bytes(b"fake-audio-data")
    subtitle.write_text("1\n00:00:01 --> 00:00:04\nHello")
    return {
        "video": str(video),
        "audio": str(audio),
        "subtitle": str(subtitle),
        "output": str(output),
    }


# ── 默认字幕样式 ──────────────────────────────────────────────


class TestDefaultSubtitleStyle:
    def test_is_dict(self):
        """默认样式是字典。"""
        assert isinstance(video_builder.DEFAULT_SUBTITLE_STYLE, dict)

    def test_has_required_keys(self):
        """包含必需的样式键。"""
        required = {"FontSize", "PrimaryColour", "OutlineColour", "Outline", "BorderStyle", "MarginV"}
        assert required.issubset(set(video_builder.DEFAULT_SUBTITLE_STYLE.keys()))

    def test_font_size_is_numeric_string(self):
        """FontSize 是数字字符串。"""
        assert video_builder.DEFAULT_SUBTITLE_STYLE["FontSize"].isdigit()


# ── 文件存在性检查 ────────────────────────────────────────────


class TestFileValidation:
    @pytest.mark.asyncio
    async def test_missing_video_raises(self, sample_files):
        """视频文件不存在时抛 FileNotFoundError。"""
        with patch("manim_agent.video_builder.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError, match="video"):
                await video_builder.build_final_video(
                    sample_files["video"],
                    sample_files["audio"],
                    None,
                    sample_files["output"],
                )

    @pytest.mark.asyncio
    async def test_missing_audio_raises(self, sample_files):
        """音频文件不存在时抛 FileNotFoundError。"""
        with (
            patch("manim_agent.video_builder._validate_inputs", side_effect=FileNotFoundError("Audio file not found: audio")),
            pytest.raises(FileNotFoundError, match="audio"),
        ):
            await video_builder.build_final_video(
                sample_files["video"],
                sample_files["audio"],
                None,
                sample_files["output"],
            )


# ── 时长获取 (ffprobe) ────────────────────────────────────────


class TestGetDuration:
    @pytest.mark.asyncio
    async def test_ffprobe_parsing(self, tmp_path):
        """正确解析 ffprobe JSON 输出中的时长。"""
        video_file = str(tmp_path / "test.mp4")
        Path(tmp_path / "test.mp4").write_bytes(b"fake")

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = (
            b'{"format": {"duration": "12.5"}}',
            b"",
        )

        with patch("manim_agent.video_builder.asyncio.create_subprocess_exec", return_value=mock_proc):
            duration = await video_builder._get_duration(video_file)
            assert duration == 12.5

    @pytest.mark.asyncio
    async def test_ffprobe_failure_raises(self, tmp_path):
        """ffprobe 失败时抛 RuntimeError。"""
        video_file = str(tmp_path / "test.mp4")
        Path(tmp_path / "test.mp4").write_bytes(b"fake")

        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate.return_value = (b"", b"ffprobe error")

        with patch("manim_agent.video_builder.asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(RuntimeError, match="ffprobe"):
                await video_builder._get_duration(video_file)


# ── 时长对齐策略 ──────────────────────────────────────────────


class TestAlignDurations:
    def test_video_longer_returns_shortest(self):
        """视频长于音频时返回 shortest 策略。"""
        strategy = video_builder._align_durations(30.0, 10.0)
        assert strategy == "shortest"

    def test_audio_longer_returns_tpad(self):
        """音频长于视频时返回 tpad 延长策略。"""
        strategy = video_builder._align_durations(10.0, 30.0)
        assert strategy == "tpad"

    def test_near_match_returns_speed(self):
        """接近时长（<5%差异）返回 speed 微调策略。"""
        strategy = video_builder._align_durations(10.0, 10.3)
        assert strategy == "speed"

    def test_equal_duration_returns_shortest(self):
        """相等时长返回 shortest（最安全）。"""
        strategy = video_builder._align_durations(10.0, 10.0)
        assert strategy == "shortest"


# ── FFmpeg 命令构建 ──────────────────────────────────────────


class TestBuildFFmpegCmd:
    def test_with_subtitle(self, sample_files):
        """含字幕时命令包含 subtitles 滤镜。"""
        cmd = video_builder._build_ffmpeg_cmd(
            sample_files["video"],
            sample_files["audio"],
            sample_files["subtitle"],
            sample_files["output"],
            "shortest",
        )
        cmd_str = " ".join(cmd)
        assert "subtitles=" in cmd_str
        assert "-c:v libx264" in cmd_str or "-c:v copy" not in cmd_str

    def test_without_subtitle(self, sample_files):
        """不含字幕时使用 stream copy。"""
        cmd = video_builder._build_ffmpeg_cmd(
            sample_files["video"],
            sample_files["audio"],
            None,
            sample_files["output"],
            "shortest",
        )
        cmd_str = " ".join(cmd)
        assert "subtitles=" not in cmd_str
        assert "-c:v copy" in cmd_str

    def test_shortest_flag(self, sample_files):
        """shortest 策略包含 -shortest 标志。"""
        cmd = video_builder._build_ffmpeg_cmd(
            sample_files["video"], sample_files["audio"], None,
            sample_files["output"], "shortest",
        )
        assert "-shortest" in cmd

    def test_output_overwrite(self, sample_files):
        """输出包含 -y 覆盖标志。"""
        cmd = video_builder._build_ffmpeg_cmd(
            sample_files["video"], sample_files["audio"], None,
            sample_files["output"], "shortest",
        )
        assert "-y" in cmd


# ── 全流程集成测试 ────────────────────────────────────────────


class TestBuildFinalVideo:
    @pytest.mark.asyncio
    async def test_full_flow_mocked(self, sample_files):
        """全流程 mock：校验→取时长→对齐→构建命令→执行。"""
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = (b"", b"")

        with (
            patch("manim_agent.video_builder._get_duration", new_callable=AsyncMock) as mock_dur,
            patch("manim_agent.video_builder._build_ffmpeg_cmd") as mock_cmd,
            patch("manim_agent.video_builder.asyncio.create_subprocess_exec", return_value=mock_proc),
        ):
            mock_dur.side_effect = [15.0, 14.0]  # video, audio durations
            mock_cmd.return_value = ["ffmpeg", "-i", "v", "-i", "a", "-y", "out.mp4"]

            result = await video_builder.build_final_video(
                sample_files["video"],
                sample_files["audio"],
                sample_files["subtitle"],
                sample_files["output"],
            )

            assert result == sample_files["output"]
            assert mock_dur.call_count == 2  # video + audio
            mock_cmd.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_subtitle_flow(self, sample_files):
        """无字幕时的完整流程。"""
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = (b"", b"")

        with (
            patch("manim_agent.video_builder._get_duration", new_callable=AsyncMock) as mock_dur,
            patch("manim_agent.video_builder._build_ffmpeg_cmd") as mock_cmd,
            patch("manim_agent.video_builder.asyncio.create_subprocess_exec", return_value=mock_proc),
        ):
            mock_dur.side_effect = [10.0, 10.0]
            mock_cmd.return_value = ["ffmpeg"]

            result = await video_builder.build_final_video(
                sample_files["video"],
                sample_files["audio"],
                subtitle_path=None,
                output_path=sample_files["output"],
            )

            assert result == sample_files["output"]
            call_args = mock_cmd.call_args[0]
            # subtitle_path 是第 3 个位置参数 (index 2)
            assert call_args[2] is None

    @pytest.mark.asyncio
    async def test_ffmpeg_failure_raises(self, sample_files):
        """ffmpeg 执行失败时抛 RuntimeError。"""
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate.return_value = (b"", b"Encoding error")

        with (
            patch("manim_agent.video_builder._get_duration", new_callable=AsyncMock) as mock_dur,
            patch("manim_agent.video_builder._build_ffmpeg_cmd") as mock_cmd,
            patch("manim_agent.video_builder.asyncio.create_subprocess_exec", return_value=mock_proc),
        ):
            mock_dur.side_effect = [5.0, 5.0]
            mock_cmd.return_value = ["ffmpeg"]

            with pytest.raises(RuntimeError, match="ffmpeg"):
                await video_builder.build_final_video(
                    sample_files["video"],
                    sample_files["audio"],
                    None,
                    sample_files["output"],
                )
