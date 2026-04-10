"""Tests for manim_agent.__main__ module (CLI entry point)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from manim_agent import __main__ as main_module


# ── CLI 参数解析 ──────────────────────────────────────────────


class TestParseArgs:
    def test_defaults(self):
        """默认参数值正确。"""
        args = main_module.parse_args(["解释傅里叶变换"])
        assert args.text == "解释傅里叶变换"
        assert args.output == "output.mp4"
        assert args.voice == "female-tianmei"
        assert args.model == "speech-2.8-hd"
        assert args.quality == "high"
        assert args.no_tts is False
        assert args.max_turns == 50

    def test_all_options(self):
        """所有参数正确解析。"""
        args = main_module.parse_args([
            "讲解二叉树",
            "-o", "tree.mp4",
            "--voice", "male-qn-qingse",
            "--model", "speech-02-hd",
            "--quality", "low",
            "--no-tts",
            "--max-turns", "20",
            "--cwd", "/workspace",
            "--prompt-file", "custom.txt",
        ])
        assert args.text == "讲解二叉树"
        assert args.output == "tree.mp4"
        assert args.voice == "male-qn-qingse"
        assert args.model == "speech-02-hd"
        assert args.quality == "low"
        assert args.no_tts is True
        assert args.max_turns == 20
        assert args.cwd == "/workspace"
        assert args.prompt_file == "custom.txt"

    def test_no_tts_flag(self):
        """--no-tts 标志生效。"""
        args = main_module.parse_args(["测试", "--no-tts"])
        assert args.no_tts is True

    def test_positional_required(self):
        """缺少位置参数时抛出 SystemExit。"""
        with pytest.raises(SystemExit):
            main_module.parse_args([])


# ── 结果提取 ──────────────────────────────────────────────────


class TestExtractResult:
    def test_extract_video_output(self):
        """从文本中提取 VIDEO_OUTPUT 路径。"""
        text = "渲染完成\nVIDEO_OUTPUT: /path/to/video.mp4\n其他信息"
        result = main_module.extract_result(text)
        assert result["video_output_path"] == "/path/to/video.mp4"

    def test_extract_scene_info(self):
        """提取 SCENE_FILE 和 SCENE_CLASS。"""
        text = (
            "VIDEO_OUTPUT: media/scene.mp4\n"
            "SCENE_FILE: scenes/fourier.py\n"
            "SCENE_CLASS: FourierScene\n"
            "DURATION: 45"
        )
        result = main_module.extract_result(text)
        assert result["scene_file"] == "scenes/fourier.py"
        assert result["scene_class"] == "FourierScene"

    def test_no_marker_returns_none(self):
        """无 VIDEO_OUTPUT 标记时路径为 None。"""
        result = main_module.extract_result("一些普通文本输出")
        assert result["video_output_path"] is None

    def test_empty_text_returns_none(self):
        """空文本返回 None 值。"""
        result = main_module.extract_result("")
        assert result["video_output_path"] is None

    def test_extract_from_message_stream(self):
        """从多行消息中提取最后一个有效结果。"""
        text = (
            "正在编写代码...\n"
            "VIDEO_OUTPUT: /tmp/attempt1.mp4\n"
            "效果不佳，重新渲染...\n"
            "VIDEO_OUTPUT: /tmp/final.mp4\n"
            "SCENE_FILE: final_scene.py\n"
            "SCENE_CLASS: FinalScene"
        )
        result = main_module.extract_result(text)
        # 应取最后一个有效的 VIDEO_OUTPUT
        assert result["video_output_path"] == "/tmp/final.mp4"


# ── Pipeline 编排（Mock 集成） ────────────────────────────────


def _make_mock_message(text: str):
    """创建模拟的 AssistantMessage，包含 .content → [.text] 结构。"""
    block = type("TextBlock", (), {"text": text})()
    return type("AssistantMessage", (), {"content": [block]})()


class TestRunPipeline:
    @pytest.mark.asyncio
    async def test_full_flow_with_tts(self):
        """含 TTS 的完整流程。"""
        mock_messages = [
            _make_mock_message("VIDEO_OUTPUT: media/out.mp4\nSCENE_FILE: s.py\nSCENE_CLASS: S"),
        ]

        with (
            patch("manim_agent.__main__.query") as mock_query,
            patch("manim_agent.__main__.tts_client.synthesize", new_callable=AsyncMock) as mock_tts,
            patch("manim_agent.__main__.video_builder.build_final_video", new_callable=AsyncMock) as mock_video,
        ):
            async def mock_query_gen(*args, **kwargs):
                for msg in mock_messages:
                    yield msg

            mock_query.side_effect = mock_query_gen

            mock_tts.return_value = MagicMock(
                audio_path="out/audio.mp3",
                subtitle_path="out/sub.srt",
                duration_ms=30000,
            )
            mock_video.return_value = "output/final.mp4"

            result = await main_module.run_pipeline(
                user_text="测试内容",
                output_path="output/final.mp4",
                voice_id="female-tianmei",
                no_tts=False,
            )

            assert result == "output/final.mp4"
            mock_tts.assert_awaited_once()
            mock_video.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skip_tts_mode(self):
        """--no-tts 模式跳过 TTS 和 video builder。"""
        mock_messages = [
            _make_mock_message("VIDEO_OUTPUT: media/silent.mp4"),
        ]

        with (
            patch("manim_agent.__main__.query") as mock_query,
            patch("manim_agent.__main__.tts_client.synthesize", new_callable=AsyncMock) as mock_tts,
            patch("manim_agent.__main__.video_builder.build_final_video", new_callable=AsyncMock) as mock_video,
        ):
            async def mock_query_gen(*args, **kwargs):
                for msg in mock_messages:
                    yield msg

            mock_query.side_effect = mock_query_gen

            result = await main_module.run_pipeline(
                user_text="测试",
                output_path="output/out.mp4",
                no_tts=True,
            )

            assert result == "media/silent.mp4"  # 直接返回 Claude 输出的视频
            mock_tts.assert_not_awaited()
            mock_video.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_video_output_raises(self):
        """Claude 未输出 VIDEO_OUTPUT 时抛 RuntimeError。"""
        mock_messages = [
            _make_mock_message("处理完成但未生成视频"),
        ]

        with (
            patch("manim_agent.__main__.query") as mock_query,
            pytest.raises(RuntimeError, match="VIDEO_OUTPUT"),
        ):
            async def mock_query_gen(*args, **kwargs):
                for msg in mock_messages:
                    yield msg

            mock_query.side_effect = mock_query_gen

            await main_module.run_pipeline(
                user_text="测试",
                output_path="output/out.mp4",
                no_tts=True,
            )
