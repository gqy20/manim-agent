"""Tests for TTS narration flow in pipeline."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from manim_agent.schemas import Phase3RenderReviewOutput as RenderReviewOutput
from manim_agent.schemas.phase3_5_narration import Phase3_5NarrationOutput

from ._test_main_dispatcher_helpers import (
    _make_assistant_message,
    _make_result_message,
    _make_text_block,
    _make_two_stage_query_side_effect,
    _phase2_output,
    main_module,
)


class TestTTSNarrationFlow:
    @pytest.mark.asyncio
    async def test_tts_receives_beat_level_narration_texts(self):
        """TTS should receive individual beat-level narration texts, not a single block."""
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

        expected_tts_texts = [
            "Introduce the intuition.",
            "Explain the core relationship.",
            "Restate the final takeaway.",
        ]

        with (
            patch("manim_agent.pipeline.query") as mock_query,
            patch(
                "manim_agent.pipeline.generate_narration",
                new_callable=AsyncMock,
                return_value=Phase3_5NarrationOutput(
                    narration="First show a circle, then morph it into a square.",
                    beat_coverage=["Introduce the intuition.", "Explain the core relationship.", "Restate the final takeaway."],
                    char_count=68,
                    generation_method="llm",
                ),
            ),
            patch("manim_agent.pipeline.tts_client.synthesize", side_effect=capture_tts),
            patch(
                "manim_agent.pipeline.video_builder.build_final_video", new_callable=AsyncMock
            ) as mock_vid,
            patch(
                "manim_agent.video_builder.concat_audios", new_callable=AsyncMock
            ) as mock_concat_audio,
            patch(
                "manim_agent.pipeline.render_review.extract_review_frames", new_callable=AsyncMock
            ) as mock_frames,
            patch("manim_agent.pipeline._run_render_review", new_callable=AsyncMock) as mock_review,
        ):
            mock_query.side_effect = _make_two_stage_query_side_effect(mock_messages)
            mock_vid.return_value = "final.mp4"
            mock_concat_audio.return_value = "audio_track.mp3"
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

        assert captured_tts_text == expected_tts_texts
