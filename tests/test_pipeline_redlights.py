"""Regression tests for callback-driven pipeline logging."""

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from manim_agent import pipeline as main_module
from manim_agent.schemas import Phase3RenderReviewOutput as RenderReviewOutput

from ._test_main_dispatcher_helpers import _make_two_stage_query_side_effect


def _phase2_output(**overrides):
    data = {
        "video_output": "/out.mp4",
        "implemented_beats": ["Hook", "Main idea", "Wrap-up"],
        "build_summary": "Built the planned teaching beats.",
        "narration": "大家好，今天我们按照计划逐步讲解这个动画，从开场到核心过程再到总结收束。",
        "deviations_from_plan": [],
    }
    data.update(overrides)
    return data


def _write_mock_scene(path):
    path.write_text(
        """
from manim import *

class GeneratedScene(Scene):
    def construct(self):
        self.beat_001_hook()
        self.beat_002_main_idea()
        self.beat_003_wrap_up()

    def beat_001_hook(self):
        self.play(FadeIn(Square()), run_time=10)
        self.wait(1)

    def beat_002_main_idea(self):
        self.play(FadeIn(Circle()), run_time=35)
        self.wait(1)

    def beat_003_wrap_up(self):
        self.play(FadeIn(Triangle()), run_time=15)
        self.wait(1)
""",
        encoding="utf-8",
    )


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
    async def test_tts_phase_logs_via_callback(self, tmp_path):
        logs: list[str] = []
        (tmp_path / "out.mp4").write_bytes(b"render")
        _write_mock_scene(tmp_path / "scene.py")
        mock_messages = [
            _make_assistant_message(_make_text_block("render complete")),
            _make_result_message(
                num_turns=1,
                structured_output=_phase2_output(
                    video_output="out.mp4",
                    scene_file="scene.py",
                    scene_class="GeneratedScene",
                ),
            ),
        ]

        with (
            patch("manim_agent.pipeline.query") as mock_query,
            patch("manim_agent.tts_client.synthesize", new_callable=AsyncMock) as mock_tts,
            patch(
                "manim_agent.video_builder.build_final_video", new_callable=AsyncMock
            ) as mock_video,
            patch(
                "manim_agent.video_builder.concat_audios", new_callable=AsyncMock
            ) as mock_concat_audio,
            patch(
                "manim_agent.render_review.extract_review_frames", new_callable=AsyncMock
            ) as mock_frames,
            patch(
                "manim_agent.pipeline._run_render_review", new_callable=AsyncMock
            ) as mock_review,
        ):
            mock_query.side_effect = _make_two_stage_query_side_effect(mock_messages)
            mock_tts.return_value = MagicMock(
                audio_path="/tmp/audio.mp3",
                subtitle_path="/tmp/sub.srt",
                duration_ms=1200,
                word_count=42,
            )
            mock_video.return_value = "/out/final.mp4"
            mock_concat_audio.return_value = str(tmp_path / "audio_track.mp3")
            mock_frames.return_value = []
            mock_review.return_value = RenderReviewOutput(
                approved=True,
                summary="Looks good.",
                blocking_issues=[],
                suggested_edits=[],
            )

            await main_module.run_pipeline(
                user_text="测试 TTS 日志",
                output_path=str(tmp_path / "final.mp4"),
                cwd=str(tmp_path),
                log_callback=logs.append,
            )

        assert any("[TTS]" in line for line in logs)

    @pytest.mark.asyncio
    async def test_mux_phase_logs_via_callback(self, tmp_path):
        logs: list[str] = []
        (tmp_path / "out.mp4").write_bytes(b"render")
        _write_mock_scene(tmp_path / "scene.py")
        mock_messages = [
            _make_assistant_message(_make_text_block("render complete")),
            _make_result_message(
                num_turns=1,
                structured_output=_phase2_output(
                    video_output="out.mp4",
                    scene_file="scene.py",
                    scene_class="GeneratedScene",
                ),
            ),
        ]
        mock_tts_result = MagicMock(
            audio_path="/tmp/audio.mp3",
            subtitle_path="/tmp/sub.srt",
            duration_ms=1200,
            word_count=42,
        )

        with (
            patch("manim_agent.pipeline.query") as mock_query,
            patch("manim_agent.tts_client.synthesize", new_callable=AsyncMock) as mock_tts,
            patch(
                "manim_agent.video_builder.build_final_video", new_callable=AsyncMock
            ) as mock_video,
            patch(
                "manim_agent.video_builder.concat_audios", new_callable=AsyncMock
            ) as mock_concat_audio,
            patch(
                "manim_agent.render_review.extract_review_frames", new_callable=AsyncMock
            ) as mock_frames,
            patch(
                "manim_agent.pipeline._run_render_review", new_callable=AsyncMock
            ) as mock_review,
        ):
            mock_query.side_effect = _make_two_stage_query_side_effect(mock_messages)
            mock_tts.return_value = mock_tts_result
            mock_video.return_value = "/out/final.mp4"
            mock_concat_audio.return_value = str(tmp_path / "audio_track.mp3")
            mock_frames.return_value = []
            mock_review.return_value = RenderReviewOutput(
                approved=True,
                summary="Looks good.",
                blocking_issues=[],
                suggested_edits=[],
            )

            await main_module.run_pipeline(
                user_text="测试 MUX 日志",
                output_path=str(tmp_path / "final.mp4"),
                cwd=str(tmp_path),
                log_callback=logs.append,
            )

        assert any("[MUX]" in line for line in logs)
