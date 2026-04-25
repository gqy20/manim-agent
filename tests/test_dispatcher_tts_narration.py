from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from manim_agent.schemas import Phase3RenderReviewOutput as RenderReviewOutput

from ._test_main_dispatcher_helpers import (
    TaskNotificationMessage,
    _make_assistant_message,
    _make_result_message,
    _make_text_block,
    _make_two_stage_query_side_effect,
    main_module,
)


def _phase2_output(**overrides):
    data = {
        "video_output": "/out.mp4",
        "implemented_beats": ["Hook", "Main idea", "Wrap-up"],
        "build_summary": "Built the planned teaching beats.",
        "deviations_from_plan": [],
    }
    data.update(overrides)
    return data


class TestTTSNarrationFlow:
    @pytest.mark.asyncio
    async def test_tts_uses_narration_when_available(self):
        mock_messages = [
            _make_assistant_message(_make_text_block("render complete")),
            _make_result_message(
                num_turns=1,
                structured_output=_phase2_output(
                    narration="First show a circle, then morph it into a square.",
                ),
            ),
        ]
        captured_tts_text: list[str] = []

        async def capture_tts(text, **_kw):
            captured_tts_text.append(text)
            return MagicMock(audio_path="a.mp3", subtitle_path="sub.srt", duration_ms=1000)

        expected_narration = "First show a circle, then morph it into a square."

        with (
            patch("manim_agent.pipeline.query") as mock_query,
            patch(
                "manim_agent.pipeline.generate_narration",
                new_callable=AsyncMock,
                return_value=expected_narration,
            ),
            patch("manim_agent.pipeline.tts_client.synthesize", side_effect=capture_tts),
            patch(
                "manim_agent.pipeline.video_builder.build_final_video", new_callable=AsyncMock
            ) as mock_vid,
            patch(
                "manim_agent.pipeline.render_review.extract_review_frames", new_callable=AsyncMock
            ) as mock_frames,
            patch("manim_agent.pipeline._run_render_review", new_callable=AsyncMock) as mock_review,
        ):
            mock_query.side_effect = _make_two_stage_query_side_effect(mock_messages)
            mock_vid.return_value = "final.mp4"
            mock_frames.return_value = []
            mock_review.return_value = RenderReviewOutput(
                approved=True,
                summary="Looks good.",
                blocking_issues=[],
                suggested_edits=[],
            )

            await main_module.run_pipeline(
                user_text="Original user text",
                output_path="/out.mp4",
                no_tts=False,
            )

        assert captured_tts_text == [expected_narration]

    @pytest.mark.asyncio
    async def test_tts_falls_back_to_user_text_when_structured_output_narration_missing(self):
        mock_messages = [
            _make_assistant_message(_make_text_block("render complete")),
            _make_result_message(
                num_turns=1,
                structured_output=_phase2_output(),
            ),
        ]
        captured_tts_text: list[str] = []

        async def capture_tts(text, **_kw):
            captured_tts_text.append(text)
            return MagicMock(audio_path="a.mp3", subtitle_path="sub.srt", duration_ms=1000)

        expected_narration = "Fallback narration from the user request."

        with (
            patch("manim_agent.pipeline.query") as mock_query,
            patch(
                "manim_agent.pipeline.generate_narration",
                new_callable=AsyncMock,
                return_value=expected_narration,
            ),
            patch("manim_agent.pipeline.tts_client.synthesize", side_effect=capture_tts),
            patch(
                "manim_agent.pipeline.video_builder.build_final_video", new_callable=AsyncMock
            ) as mock_vid,
            patch(
                "manim_agent.pipeline.render_review.extract_review_frames", new_callable=AsyncMock
            ) as mock_frames,
            patch("manim_agent.pipeline._run_render_review", new_callable=AsyncMock) as mock_review,
        ):
            mock_query.side_effect = _make_two_stage_query_side_effect(mock_messages)
            mock_vid.return_value = "final.mp4"
            mock_frames.return_value = []
            mock_review.return_value = RenderReviewOutput(
                approved=True,
                summary="Looks good.",
                blocking_issues=[],
                suggested_edits=[],
            )

            await main_module.run_pipeline(
                user_text="Fallback narration from the user request.",
                output_path="/out.mp4",
                no_tts=False,
            )

        assert captured_tts_text == [expected_narration]

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
                structured_output=_phase2_output(
                    video_output="/ignored.mp4",
                    narration="Narration from structured output.",
                ),
            ),
        ]
        captured_tts_text: list[str] = []

        async def capture_tts(text, **_kw):
            captured_tts_text.append(text)
            return MagicMock(audio_path="a.mp3", subtitle_path="sub.srt", duration_ms=1000)

        expected_narration = "Narration from structured output."

        with (
            patch("manim_agent.pipeline.query") as mock_query,
            patch(
                "manim_agent.pipeline.generate_narration",
                new_callable=AsyncMock,
                return_value=expected_narration,
            ),
            patch("manim_agent.pipeline.tts_client.synthesize", side_effect=capture_tts),
            patch(
                "manim_agent.pipeline.video_builder.build_final_video", new_callable=AsyncMock
            ) as mock_vid,
            patch(
                "manim_agent.pipeline.render_review.extract_review_frames", new_callable=AsyncMock
            ) as mock_frames,
            patch("manim_agent.pipeline._run_render_review", new_callable=AsyncMock) as mock_review,
        ):
            mock_query.side_effect = _make_two_stage_query_side_effect(mock_messages)
            mock_vid.return_value = "final.mp4"
            mock_frames.return_value = []
            mock_review.return_value = RenderReviewOutput(
                approved=True,
                summary="Looks good.",
                blocking_issues=[],
                suggested_edits=[],
            )

            await main_module.run_pipeline(
                user_text="Original user text",
                output_path="/out.mp4",
                no_tts=False,
            )

        assert captured_tts_text == [expected_narration]
