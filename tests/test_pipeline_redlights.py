"""Regression tests for callback-driven pipeline logging."""

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from manim_agent import pipeline as main_module
from manim_agent.schemas import Phase3RenderReviewOutput as RenderReviewOutput
from manim_agent.schemas.phase3_5_narration import Phase3_5NarrationOutput

from ._test_main_dispatcher_helpers import (
    _DEFAULT_DRAFT_SOURCE,
    _make_assistant_message,
    _make_result_message,
    _make_text_block,
    _make_two_stage_query_side_effect,
    _phase2_output,
)


def _write_mock_scene(path):
    path.write_text(_DEFAULT_DRAFT_SOURCE, encoding="utf-8")


def _write_mock_tts_artifact(tmp_path):
    audio_path = tmp_path / "audio" / "beat_001" / "audio.mp3"
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(b"fake-mp3")
    return audio_path


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
            patch(
                "manim_agent.pipeline.generate_narration",
                new_callable=AsyncMock,
                return_value=Phase3_5NarrationOutput(
                    narration="测试口播文案内容。",
                    beat_coverage=["第一部分", "第二部分"],
                    char_count=10,
                    generation_method="llm",
                ),
            ),
        ):
            mock_query.side_effect = _make_two_stage_query_side_effect(mock_messages)
            audio_path = _write_mock_tts_artifact(tmp_path)
            mock_tts.return_value = MagicMock(
                audio_path=str(audio_path),
                subtitle_path="",
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
        audio_path = _write_mock_tts_artifact(tmp_path)
        mock_tts_result = MagicMock(
            audio_path=str(audio_path),
            subtitle_path="",
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
            patch(
                "manim_agent.pipeline.generate_narration",
                new_callable=AsyncMock,
                return_value=Phase3_5NarrationOutput(
                    narration="测试 MUX 口播文案。",
                    beat_coverage=["第一部分"],
                    char_count=9,
                    generation_method="llm",
                ),
            ),
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
