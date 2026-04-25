from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from manim_agent.schemas import Phase3RenderReviewOutput as RenderReviewOutput

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
async def test_pipeline_falls_back_to_voice_only_when_bgm_generation_fails(tmp_path):
    render_path = tmp_path / "media" / "out.mp4"
    render_path.parent.mkdir(parents=True, exist_ok=True)
    render_path.write_bytes(b"render")

    planning_messages = [
        _make_result_message(
            num_turns=1,
            **{
                "structured_output": {
                    "build_spec": {
                        "mode": "concept-explainer",
                        "learning_goal": "Explain the topic clearly.",
                        "audience": "Beginners",
                        "target_duration_seconds": 60,
                        "beats": [
                            {
                                "id": "beat_001_opening",
                                "title": "Opening",
                                "visual_goal": "Introduce the topic.",
                                "narration_intent": "Opening line",
                                "target_duration_seconds": 20,
                                "required_elements": [],
                                "segment_required": True,
                            },
                            {
                                "id": "beat_002_main_idea",
                                "title": "Main idea",
                                "visual_goal": "Explain the main concept.",
                                "narration_intent": "Main explanation",
                                "target_duration_seconds": 40,
                                "required_elements": [],
                                "segment_required": True,
                            },
                        ],
                    },
                }
            },
        ),
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
        patch(
            "manim_agent.pipeline.video_builder._get_duration",
            new_callable=AsyncMock,
            return_value=60.0,
        ),
        patch("manim_agent.pipeline.run_phase3_render", new_callable=AsyncMock) as mock_phase3,
        patch("manim_agent.pipeline.tts_client.synthesize", new_callable=AsyncMock) as mock_tts,
        patch(
            "manim_agent.pipeline.music_client.generate_instrumental",
            new_callable=AsyncMock,
            side_effect=RuntimeError("bgm unavailable"),
        ) as mock_bgm,
        patch(
            "manim_agent.audio_orchestrator.video_builder.concat_audios",
            new_callable=AsyncMock,
            return_value="out/audio_track.mp3",
        ),
        patch(
            "manim_agent.pipeline.video_builder.build_final_video", new_callable=AsyncMock
        ) as mock_mux,
    ):
        mock_phase3.return_value = (
            MagicMock(
                narration="Narration for the finished video.",
                duration_seconds=60.0,
                scene_file="scene.py",
                scene_class="GeneratedScene",
                implemented_beats=["Opening", "Main idea"],
                build_summary="Built the planned animation beats.",
                beat_to_narration_map=["Opening -> intro", "Main idea -> explanation"],
                narration_coverage_complete=True,
                estimated_narration_duration_seconds=60.0,
            ),
            str(render_path.resolve()),
            ["frame-1.png"],
        )
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
            cwd=str(tmp_path),
    )

    assert result == "output/final.mp4"
    assert mock_tts.await_count >= 1
    mock_bgm.assert_awaited_once()
    mock_mux.assert_awaited_once_with(
        video_path=str(render_path.resolve()),
        audio_path="out/audio_track.mp3",
        subtitle_path=None,
        output_path="output/final.mp4",
        bgm_path=None,
        bgm_volume=0.12,
    )
