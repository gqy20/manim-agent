from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ._test_main_dispatcher_helpers import (
    _make_assistant_message,
    _make_result_message,
    _make_text_block,
    TaskNotificationMessage,
    main_module,
)


class TestTTSNarrationFlow:
    @pytest.mark.asyncio
    async def test_tts_uses_narration_when_available(self):
        mock_messages = [
            _make_assistant_message(_make_text_block("render complete")),
            _make_result_message(
                num_turns=1,
                **{
                    "structured_output": {
                        "video_output": "/out.mp4",
                        "narration": "专业中文解说词。",
                    }
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
                for m in mock_messages:
                    yield m

            mock_query.side_effect = gen
            mock_vid.return_value = "final.mp4"

            await main_module.run_pipeline(
                user_text="原始用户文本",
                output_path="/out.mp4",
                no_tts=False,
            )

        assert captured_tts_text == ["专业中文解说词。"]

    @pytest.mark.asyncio
    async def test_tts_falls_back_to_user_text_when_narration_missing(self):
        mock_messages = [
            _make_assistant_message(_make_text_block("render complete")),
            _make_result_message(
                num_turns=1,
                **{"structured_output": {"video_output": "/out.mp4"}},
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
                for m in mock_messages:
                    yield m

            mock_query.side_effect = gen
            mock_vid.return_value = "final.mp4"

            await main_module.run_pipeline(
                user_text="原始用户文本",
                output_path="/out.mp4",
                no_tts=False,
            )

        assert captured_tts_text == ["原始用户文本"]

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
                **{
                    "structured_output": {
                        "video_output": "/ignored.mp4",
                        "narration": "这是来自 structured output 的中文解说。",
                    }
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
                for m in mock_messages:
                    yield m

            mock_query.side_effect = gen
            mock_vid.return_value = "final.mp4"

            await main_module.run_pipeline(
                user_text="原始用户文本",
                output_path="/out.mp4",
                no_tts=False,
            )

        assert captured_tts_text == ["这是来自 structured output 的中文解说。"]
