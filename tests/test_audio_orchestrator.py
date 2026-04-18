from unittest.mock import AsyncMock, patch

import pytest

from manim_agent.audio_orchestrator import (
    build_beats_from_pipeline_output,
    orchestrate_audio_assets,
)


class TestBuildBeatsFromPipelineOutput:
    def test_uses_implemented_beats_and_narration_hints(self):
        beats = build_beats_from_pipeline_output(
            implemented_beats=["Opening", "Main Idea"],
            beat_to_narration_map=[
                "Opening -> Introduce the problem",
                "Main Idea -> Explain the core transformation",
            ],
        )

        assert [beat.id for beat in beats] == ["beat_001", "beat_002"]
        assert [beat.title for beat in beats] == ["Opening", "Main Idea"]
        assert beats[0].narration_hint == "Introduce the problem"
        assert beats[1].narration_hint == "Explain the core transformation"

    def test_falls_back_to_single_beat_when_pipeline_output_is_sparse(self):
        beats = build_beats_from_pipeline_output(
            implemented_beats=[],
            beat_to_narration_map=[],
            fallback_narration="Fallback narration from the user request.",
        )

        assert len(beats) == 1
        assert beats[0].id == "beat_001"
        assert beats[0].title == "Main narration"
        assert beats[0].narration_text == "Fallback narration from the user request."


class TestOrchestrateAudioAssets:
    @pytest.mark.asyncio
    async def test_runs_tts_and_bgm_tasks_in_parallel_and_returns_timeline(self, tmp_path):
        po = type(
            "PO",
            (),
            {
                "implemented_beats": ["Opening", "Main Idea"],
                "beat_to_narration_map": [
                    "Opening -> Introduce the topic",
                    "Main Idea -> Explain the result",
                ],
                "narration": "Introduce the topic. Explain the result.",
                "build_summary": "Built two teaching beats.",
            },
        )()

        tts_calls = []

        async def fake_generate_beat_narrations(**kwargs):
            beats = kwargs["beats"]
            beats[0].narration_text = "Introduce the topic."
            beats[1].narration_text = "Explain the result."
            return beats

        async def fake_synthesize_beat_tts(**kwargs):
            beats = kwargs["beats"]
            tts_calls.extend(beat.id for beat in beats)
            for index, beat in enumerate(beats, start=1):
                beat.audio_path = str(tmp_path / f"{beat.id}.mp3")
                beat.actual_audio_duration_seconds = float(index)
                beat.tts_mode = "sync"
            return beats

        async def fake_generate_bgm(**_kwargs):
            return str(tmp_path / "bgm.mp3"), 9000, "bgm prompt"

        async def fake_concat_audios(audio_paths, output_path):
            assert len(audio_paths) == 2
            return output_path

        with (
            patch(
                "manim_agent.audio_orchestrator.generate_beat_narrations",
                side_effect=fake_generate_beat_narrations,
            ),
            patch(
                "manim_agent.audio_orchestrator.synthesize_beat_tts",
                side_effect=fake_synthesize_beat_tts,
            ),
            patch(
                "manim_agent.audio_orchestrator.maybe_generate_bgm",
                side_effect=fake_generate_bgm,
            ),
            patch(
                "manim_agent.audio_orchestrator.video_builder.concat_audios",
                side_effect=fake_concat_audios,
            ),
        ):
            result = await orchestrate_audio_assets(
                po=po,
                user_text="Explain a transformation",
                plan_text="Plan text",
                target_duration_seconds=30,
                voice_id="female-tianmei",
                model="speech-2.8-hd",
                output_dir=str(tmp_path),
                bgm_enabled=True,
                bgm_prompt=None,
                preset="educational",
            )

        assert tts_calls == ["beat_001", "beat_002"]
        assert result.timeline.total_duration_seconds == 3.0
        assert result.timeline.beats[0].start_seconds == 0.0
        assert result.timeline.beats[1].start_seconds == 1.0
        assert result.concatenated_audio_path == str(tmp_path / "audio_track.mp3")
        assert result.bgm_path == str(tmp_path / "bgm.mp3")
