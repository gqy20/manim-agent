from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from manim_agent.review_schema import RenderReviewOutput

from ._test_main_dispatcher_helpers import (
    _make_assistant_message,
    _make_result_message,
    _make_text_block,
    main_module,
)


PLAN_TEXT = """# Mode
concept-explainer

# Learning Goal
Explain the topic clearly.

# Audience
Beginners

# Beat List
1. Opening
2. Main idea

# Narration Outline
- Opening line
- Main explanation

# Visual Risks
- Too dense

# Build Handoff
Skill Signature: mp-scene-plan-v1
"""


@pytest.mark.asyncio
async def test_pipeline_falls_back_to_voice_only_when_bgm_generation_fails():
    planning_messages = [
        _make_assistant_message(_make_text_block(PLAN_TEXT)),
        _make_result_message(num_turns=1),
    ]
    build_messages = [
        _make_assistant_message(_make_text_block("implementation complete")),
        _make_result_message(
            num_turns=1,
            **{
                "structured_output": {
                    "video_output": "media/out.mp4",
                    "scene_file": "scene.py",
                    "scene_class": "GeneratedScene",
                    "narration": "Narration for the finished video.",
                    "implemented_beats": ["Opening", "Main idea"],
                    "build_summary": "Built the planned animation beats.",
                    "deviations_from_plan": [],
                    "beat_to_narration_map": ["Opening -> intro", "Main idea -> explanation"],
                    "narration_coverage_complete": True,
                    "estimated_narration_duration_seconds": 12.0,
                }
            },
        ),
    ]

    async def mock_query_gen(*args, **kwargs):
        prompt = kwargs.get("prompt", "")
        messages = planning_messages if "Planning pass only" in prompt else build_messages
        for msg in messages:
            yield msg

    with (
        patch("manim_agent.pipeline.query", side_effect=mock_query_gen),
        patch(
            "manim_agent.pipeline.render_review.extract_review_frames",
            new_callable=AsyncMock,
            return_value=["frame-1.png"],
        ),
        patch(
            "manim_agent.pipeline._run_render_review",
            new_callable=AsyncMock,
            return_value=RenderReviewOutput(
                summary="Looks good.",
                approved=True,
                blocking_issues=[],
                suggested_edits=[],
            ),
        ),
        patch("manim_agent.pipeline.video_builder._get_duration", new_callable=AsyncMock, return_value=60.0),
        patch("manim_agent.pipeline.tts_client.synthesize", new_callable=AsyncMock) as mock_tts,
        patch(
            "manim_agent.pipeline.music_client.generate_instrumental",
            new_callable=AsyncMock,
            side_effect=RuntimeError("bgm unavailable"),
        ) as mock_bgm,
        patch("manim_agent.pipeline.video_builder.build_final_video", new_callable=AsyncMock) as mock_mux,
    ):
        mock_tts.return_value = MagicMock(
            audio_path="out/audio.mp3",
            subtitle_path="out/sub.srt",
            duration_ms=12000,
            word_count=80,
            extra_info_path="out/extra.json",
            usage_characters=80,
            mode="sync",
        )
        mock_mux.return_value = "output/final.mp4"

        result = await main_module.run_pipeline(
            user_text="Explain a concept with narration and optional BGM",
            output_path="output/final.mp4",
            no_tts=False,
            bgm_enabled=True,
            target_duration_seconds=60,
        )

    assert result == "output/final.mp4"
    mock_tts.assert_awaited_once()
    mock_bgm.assert_awaited_once()
    mock_mux.assert_awaited_once_with(
        video_path=str(Path("media/out.mp4").resolve()),
        audio_path="out/audio.mp3",
        subtitle_path="out/sub.srt",
        output_path="output/final.mp4",
        bgm_path=None,
        bgm_volume=0.12,
    )
