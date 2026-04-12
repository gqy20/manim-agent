"""Regression tests for callback-driven pipeline logging."""

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from manim_agent import __main__ as main_module


def _make_text_block(text: str):
    from claude_agent_sdk import TextBlock

    return TextBlock(text=text)


def _make_assistant_message(*blocks):
    from claude_agent_sdk import AssistantMessage

    return AssistantMessage(content=list(blocks), model="claude-sonnet-4-20250514")


def _make_result_message(**overrides):
    from claude_agent_sdk import ResultMessage

    defaults = dict(
        subtype="result",
        duration_ms=5000,
        duration_api_ms=4500,
        is_error=False,
        num_turns=3,
        session_id="sess-abc",
        stop_reason="end_turn",
        total_cost_usd=0.0123,
        usage={"input_tokens": 1000, "output_tokens": 2000},
    )
    defaults.update(overrides)
    return ResultMessage(**defaults)


class TestStderrHandlerForwardsToCallback:
    def test_stderr_handler_accepts_callback(self):
        params = inspect.signature(main_module._stderr_handler).parameters
        assert "log_callback" in params

    def test_stderr_handler_forwards_all_lines(self):
        lines = [
            "Error: connection refused",
            "Warning: rate limit approaching",
            "Using model claude-sonnet-4-20250514",
            "Session resumed: sess-abc123",
            "Tool output: exit code 0",
        ]
        forwarded: list[str] = []

        for line in lines:
            main_module._stderr_handler(line, log_callback=forwarded.append)

        assert forwarded == [f"[CLI] {line}" for line in lines]


class TestPipelinePhaseLogsViaCallback:
    @pytest.mark.asyncio
    async def test_tts_phase_logs_via_callback(self):
        logs: list[str] = []
        mock_messages = [
            _make_assistant_message(_make_text_block("render complete")),
            _make_result_message(num_turns=1, structured_output={"video_output": "/out.mp4"}),
        ]

        with (
            patch("manim_agent.__main__.query") as mock_query,
            patch("manim_agent.__main__.tts_client.synthesize", new_callable=AsyncMock) as mock_tts,
            patch("manim_agent.__main__.video_builder.build_final_video", new_callable=AsyncMock) as mock_video,
        ):
            async def mock_query_gen(*_args, **_kwargs):
                for msg in mock_messages:
                    yield msg

            mock_query.side_effect = mock_query_gen
            mock_tts.return_value = MagicMock(
                audio_path="/tmp/audio.mp3",
                subtitle_path="/tmp/sub.srt",
                duration_ms=1200,
                word_count=42,
            )
            mock_video.return_value = "/out/final.mp4"

            await main_module.run_pipeline(
                user_text="测试 TTS 日志",
                output_path="output/out.mp4",
                log_callback=logs.append,
            )

        assert any("[TTS]" in line for line in logs)

    @pytest.mark.asyncio
    async def test_mux_phase_logs_via_callback(self):
        logs: list[str] = []
        mock_messages = [
            _make_assistant_message(_make_text_block("render complete")),
            _make_result_message(num_turns=1, structured_output={"video_output": "/out.mp4"}),
        ]
        mock_tts_result = MagicMock(
            audio_path="/tmp/audio.mp3",
            subtitle_path="/tmp/sub.srt",
            duration_ms=1200,
            word_count=42,
        )

        with (
            patch("manim_agent.__main__.query") as mock_query,
            patch("manim_agent.__main__.tts_client.synthesize", new_callable=AsyncMock) as mock_tts,
            patch("manim_agent.__main__.video_builder.build_final_video", new_callable=AsyncMock) as mock_video,
        ):
            async def mock_query_gen(*_args, **_kwargs):
                for msg in mock_messages:
                    yield msg

            mock_query.side_effect = mock_query_gen
            mock_tts.return_value = mock_tts_result
            mock_video.return_value = "/out/final.mp4"

            await main_module.run_pipeline(
                user_text="测试 MUX 日志",
                output_path="output/out.mp4",
                log_callback=logs.append,
            )

        assert any("[MUX]" in line for line in logs)
