"""Tests for manim_agent.video_builder."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from manim_agent import video_builder


@pytest.fixture
def sample_files(tmp_path):
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


class TestDefaultSubtitleStyle:
    def test_is_dict(self):
        assert isinstance(video_builder.DEFAULT_SUBTITLE_STYLE, dict)

    def test_has_required_keys(self):
        required = {"FontSize", "PrimaryColour", "OutlineColour", "Outline", "BorderStyle", "MarginV"}
        assert required.issubset(set(video_builder.DEFAULT_SUBTITLE_STYLE.keys()))


class TestFileValidation:
    @pytest.mark.asyncio
    async def test_missing_video_raises(self, sample_files):
        with patch("manim_agent.video_builder.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError, match="Video file not found"):
                await video_builder.build_final_video(
                    sample_files["video"],
                    sample_files["audio"],
                    None,
                    sample_files["output"],
                )

    @pytest.mark.asyncio
    async def test_missing_audio_raises(self, sample_files):
        with (
            patch(
                "manim_agent.video_builder._validate_inputs",
                side_effect=FileNotFoundError("Audio file not found: audio"),
            ),
            pytest.raises(FileNotFoundError, match="Audio file not found"),
        ):
            await video_builder.build_final_video(
                sample_files["video"],
                sample_files["audio"],
                None,
                sample_files["output"],
            )


class TestGetDuration:
    @pytest.mark.asyncio
    async def test_ffprobe_parsing(self, tmp_path):
        video_file = str(tmp_path / "test.mp4")
        Path(video_file).write_bytes(b"fake")

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = (b'{"format": {"duration": "12.5"}}', b"")

        with patch("manim_agent.video_builder.asyncio.create_subprocess_exec", return_value=mock_proc):
            duration = await video_builder._get_duration(video_file)
            assert duration == 12.5

    @pytest.mark.asyncio
    async def test_ffprobe_failure_raises(self, tmp_path):
        video_file = str(tmp_path / "test.mp4")
        Path(video_file).write_bytes(b"fake")

        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate.return_value = (b"", b"ffprobe error")

        with patch("manim_agent.video_builder.asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(RuntimeError, match="ffprobe failed"):
                await video_builder._get_duration(video_file)


class TestAlignDurations:
    def test_video_longer_returns_pad_audio(self):
        assert video_builder._align_durations(30.0, 10.0) == "pad_audio"

    def test_audio_longer_returns_tpad(self):
        assert video_builder._align_durations(10.0, 30.0) == "tpad"

    def test_near_match_returns_speed(self):
        assert video_builder._align_durations(10.0, 10.3) == "speed"

    def test_equal_duration_returns_shortest(self):
        assert video_builder._align_durations(10.0, 10.0) == "shortest"


class TestBuildFFmpegCmd:
    def test_with_subtitle(self, sample_files):
        cmd = video_builder._build_ffmpeg_cmd(
            sample_files["video"],
            sample_files["audio"],
            sample_files["subtitle"],
            sample_files["output"],
            "shortest",
            10.0,
            10.0,
        )
        cmd_str = " ".join(cmd)
        assert "subtitles=" in cmd_str
        assert "-c:v libx264" in cmd_str

    def test_with_bgm_builds_mix_filter(self, sample_files):
        bgm = str(Path(sample_files["video"]).with_name("bgm.mp3"))
        Path(bgm).write_bytes(b"fake-bgm-data")

        cmd = video_builder._build_ffmpeg_cmd(
            sample_files["video"],
            sample_files["audio"],
            None,
            sample_files["output"],
            "shortest",
            10.0,
            10.0,
            None,
            bgm,
            0.12,
        )

        cmd_str = " ".join(cmd)
        assert "-filter_complex" in cmd
        assert "amix=inputs=2" in cmd_str
        assert "volume=0.120" in cmd_str
        assert "[mix]" in cmd

    def test_without_subtitle_uses_stream_copy(self, sample_files):
        cmd = video_builder._build_ffmpeg_cmd(
            sample_files["video"],
            sample_files["audio"],
            None,
            sample_files["output"],
            "shortest",
            10.0,
            10.0,
        )
        cmd_str = " ".join(cmd)
        assert "subtitles=" not in cmd_str
        assert "-c:v copy" in cmd_str

    def test_shortest_flag(self, sample_files):
        cmd = video_builder._build_ffmpeg_cmd(
            sample_files["video"],
            sample_files["audio"],
            None,
            sample_files["output"],
            "shortest",
            10.0,
            10.0,
        )
        assert "-shortest" in cmd

    def test_pad_audio_keeps_full_video(self, sample_files):
        cmd = video_builder._build_ffmpeg_cmd(
            sample_files["video"],
            sample_files["audio"],
            None,
            sample_files["output"],
            "pad_audio",
            30.0,
            10.0,
        )
        assert "-af" in cmd
        assert "apad" in cmd
        assert "-t" in cmd
        assert "-shortest" not in cmd

    def test_output_overwrite(self, sample_files):
        cmd = video_builder._build_ffmpeg_cmd(
            sample_files["video"],
            sample_files["audio"],
            None,
            sample_files["output"],
            "shortest",
            10.0,
            10.0,
        )
        assert "-y" in cmd


class TestBuildFinalVideo:
    @pytest.mark.asyncio
    async def test_full_flow_mocked(self, sample_files):
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = (b"", b"")

        with (
            patch("manim_agent.video_builder._get_duration", new_callable=AsyncMock) as mock_dur,
            patch("manim_agent.video_builder._build_ffmpeg_cmd") as mock_cmd,
            patch("manim_agent.video_builder.asyncio.create_subprocess_exec", return_value=mock_proc),
        ):
            mock_dur.side_effect = [15.0, 14.0]
            mock_cmd.return_value = ["ffmpeg", "-i", "v", "-i", "a", "-y", "out.mp4"]

            result = await video_builder.build_final_video(
                sample_files["video"],
                sample_files["audio"],
                sample_files["subtitle"],
                sample_files["output"],
            )

            assert result == sample_files["output"]
            assert mock_dur.call_count == 2
            mock_cmd.assert_called_once_with(
                sample_files["video"],
                sample_files["audio"],
                sample_files["subtitle"],
                sample_files["output"],
                "pad_audio",
                15.0,
                14.0,
                None,
                None,
                0.12,
            )

    @pytest.mark.asyncio
    async def test_ffmpeg_failure_raises(self, sample_files):
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

            with pytest.raises(RuntimeError, match="ffmpeg failed"):
                await video_builder.build_final_video(
                    sample_files["video"],
                    sample_files["audio"],
                    None,
                    sample_files["output"],
                )
