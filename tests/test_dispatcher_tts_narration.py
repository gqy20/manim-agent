from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ._test_main_dispatcher_helpers import (
    TaskNotificationMessage,
    _make_assistant_message,
    _make_result_message,
    _make_text_block,
    main_module,
)


class TestTTSNarrationFlow:
    @pytest.mark.asyncio
    async def test_tts_uses_narration_when_available(self):
        mock_messages = [
            _make_assistant_message(_make_text_block("render complete")),
            _make_result_message(
                num_turns=1,
                structured_output={
                    "video_output": "/out.mp4",
                    "narration": "先展示一个圆形，再平滑变成正方形，最后出现方圆相生。",
                },
            ),
        ]
        captured_tts_text: list[str] = []

        async def capture_tts(text, **_kw):
            captured_tts_text.append(text)
            return MagicMock(audio_path="a.mp3", subtitle_path="sub.srt", duration_ms=1000)

        with (
            patch("manim_agent.__main__.query") as mock_query,
            patch("manim_agent.__main__.tts_client.synthesize", side_effect=capture_tts),
            patch("manim_agent.__main__.video_builder.build_final_video", new_callable=AsyncMock) as mock_vid,
        ):
            async def gen(*_a, **_k):
                for message in mock_messages:
                    yield message

            mock_query.side_effect = gen
            mock_vid.return_value = "final.mp4"

            await main_module.run_pipeline(
                user_text="原始用户文本",
                output_path="/out.mp4",
                no_tts=False,
            )

        assert captured_tts_text == ["先展示一个圆形，再平滑变成正方形，最后出现方圆相生。"]

    @pytest.mark.asyncio
    async def test_tts_requires_structured_output_narration(self):
        mock_messages = [
            _make_assistant_message(_make_text_block("render complete")),
            _make_result_message(
                num_turns=1,
                structured_output={"video_output": "/out.mp4"},
            ),
        ]

        with (
            patch("manim_agent.__main__.query") as mock_query,
            patch("manim_agent.__main__.tts_client.synthesize", new_callable=AsyncMock) as mock_tts,
            patch("manim_agent.__main__.video_builder.build_final_video", new_callable=AsyncMock) as mock_vid,
            pytest.raises(RuntimeError, match="structured_output\\.narration"),
        ):
            async def gen(*_a, **_k):
                for message in mock_messages:
                    yield message

            mock_query.side_effect = gen
            mock_vid.return_value = "final.mp4"

            await main_module.run_pipeline(
                user_text="请生成一个中文讲解短动画：圆形平滑变成正方形，最后显示“方圆相生”。",
                output_path="/out.mp4",
                no_tts=False,
            )

        mock_tts.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_tts_uses_merged_narration_after_task_notification(self):
        mock_messages = [
            TaskNotificationMessage(
                subtype="task_notification",
                task_id="task-1",
                status="completed",
                output_file="/out.mp4",
                summary="done",
                uuid="u1",
                session_id="s1",
                data={},
            ),
            _make_result_message(
                num_turns=1,
                structured_output={
                    "video_output": "/ignored.mp4",
                    "narration": "这是来自 structured output 的中文解说。",
                },
            ),
        ]
        captured_tts_text: list[str] = []

        async def capture_tts(text, **_kw):
            captured_tts_text.append(text)
            return MagicMock(audio_path="a.mp3", subtitle_path="sub.srt", duration_ms=1000)

        with (
            patch("manim_agent.__main__.query") as mock_query,
            patch("manim_agent.__main__.tts_client.synthesize", side_effect=capture_tts),
            patch("manim_agent.__main__.video_builder.build_final_video", new_callable=AsyncMock) as mock_vid,
        ):
            async def gen(*_a, **_k):
                for message in mock_messages:
                    yield message

            mock_query.side_effect = gen
            mock_vid.return_value = "final.mp4"

            await main_module.run_pipeline(
                user_text="原始用户文本",
                output_path="/out.mp4",
                no_tts=False,
            )

        assert captured_tts_text == ["这是来自 structured output 的中文解说。"]
