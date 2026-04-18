from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from manim_agent.beat_schema import AudioOrchestrationResult, BeatSpec, TimelineSpec
from manim_agent.dispatcher import _MessageDispatcher
from manim_agent.pipeline_phases345 import run_phase3_render, run_phase4_tts, run_phase5_mux
from manim_agent.segment_renderer import SegmentRenderPlan


class TestPipelineAudioPhases:
    @pytest.mark.asyncio
    async def test_run_phase3_render_discovers_existing_segment_videos(self, tmp_path):
        dispatcher = _MessageDispatcher(verbose=False, output_cwd=str(tmp_path))
        po = SimpleNamespace(
            video_output="media/out.mp4",
            duration_seconds=4.0,
            implemented_beats=["Opening", "Main idea"],
            beat_to_narration_map=["Opening -> intro", "Main idea -> explain"],
            build_summary="Built two beats.",
            deviations_from_plan=[],
            narration_coverage_complete=True,
            estimated_narration_duration_seconds=4.0,
            segment_video_paths=[],
            scene_file=None,
            scene_class=None,
        )
        segment_a = tmp_path / "segments" / "beat_001.mp4"
        segment_b = tmp_path / "segments" / "beat_002.mp4"
        segment_a.parent.mkdir(parents=True, exist_ok=True)
        segment_a.write_bytes(b"a")
        segment_b.write_bytes(b"b")
        review_result = SimpleNamespace(
            summary="Looks good.",
            approved=True,
            blocking_issues=[],
            suggested_edits=[],
            frame_analyses=[],
            vision_analysis_used=False,
        )

        with (
            patch.object(dispatcher, "get_pipeline_output", return_value=po),
            patch(
                "manim_agent.pipeline_phases345.extract_review_frames",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "manim_agent.pipeline_phases345.run_render_review",
                new_callable=AsyncMock,
                return_value=review_result,
            ),
        ):
            result_po, video_output, review_frames = await run_phase3_render(
                dispatcher=dispatcher,
                hook_state=SimpleNamespace(captured_source_code={}),
                user_text="Explain a concept",
                plan_text="Plan",
                result_summary=None,
                target_duration_seconds=30,
                resolved_cwd=str(tmp_path),
                system_prompt="system",
                quality="high",
                prompt_file=None,
                log_callback=None,
                event_callback=None,
                cli_stderr_lines=[],
            )

        assert result_po is po
        assert video_output == "media/out.mp4"
        assert review_frames == []
        assert po.segment_video_paths == [str(segment_a), str(segment_b)]

    @pytest.mark.asyncio
    async def test_run_phase4_tts_updates_pipeline_output_with_audio_orchestration(self, tmp_path):
        dispatcher = _MessageDispatcher(verbose=False, output_cwd=str(tmp_path))
        po = SimpleNamespace(
            duration_seconds=4.0,
            implemented_beats=["Opening", "Main idea"],
            beat_to_narration_map=["Opening -> intro", "Main idea -> explain"],
            narration="Narration",
            build_summary="Built two beats.",
        )
        audio_result = AudioOrchestrationResult(
            beats=[
                BeatSpec(
                    id="beat_001",
                    title="Opening",
                    narration_text="intro",
                    audio_path="out/beat_1.mp3",
                    actual_audio_duration_seconds=1.0,
                    tts_mode="sync",
                ),
                BeatSpec(
                    id="beat_002",
                    title="Main idea",
                    narration_text="explain",
                    audio_path="out/beat_2.mp3",
                    actual_audio_duration_seconds=2.0,
                    tts_mode="sync",
                ),
            ],
            timeline=TimelineSpec(
                beats=[
                    BeatSpec(id="beat_001", title="Opening", start_seconds=0.0, end_seconds=1.0),
                    BeatSpec(id="beat_002", title="Main idea", start_seconds=1.0, end_seconds=3.0),
                ],
                total_duration_seconds=3.0,
            ),
            timeline_path="out/timeline.json",
            concatenated_audio_path="out/audio_track.mp3",
            concatenated_subtitle_path="out/subtitles.srt",
            bgm_path="out/bgm.mp3",
            bgm_duration_ms=9000,
            bgm_prompt="bgm prompt",
        )

        with patch(
            "manim_agent.pipeline_phases345.orchestrate_audio_assets",
            new_callable=AsyncMock,
            return_value=audio_result,
        ):
            result = await run_phase4_tts(
                dispatcher=dispatcher,
                narration_text="Narration",
                video_output="media/out.mp4",
                voice_id="female-tianmei",
                model="speech-2.8-hd",
                output_path=str(tmp_path / "final.mp4"),
                po=po,
                user_text="Explain a concept",
                plan_text="Plan",
                target_duration_seconds=30,
                bgm_enabled=True,
                bgm_prompt=None,
                preset="educational",
                event_callback=None,
            )

        assert result is audio_result
        assert po.audio_path == "out/audio_track.mp3"
        assert po.subtitle_path == "out/subtitles.srt"
        assert po.timeline_path == "out/timeline.json"
        assert po.timeline_total_duration_seconds == 3.0
        assert po.audio_mix_mode == "voice_with_bgm"
        assert len(po.beats) == 2
        assert len(po.audio_segments) == 2
        assert po.segment_render_plan_path.endswith("segment_render_plan.json")
        assert po.segment_video_paths[0].endswith("segments\\beat_001.mp4")

    @pytest.mark.asyncio
    async def test_run_phase5_mux_uses_concatenated_audio_assets(self, tmp_path):
        dispatcher = _MessageDispatcher(verbose=False, output_cwd=str(tmp_path))
        po = SimpleNamespace(
            final_video_output=None,
            intro_video_path=None,
            outro_video_path=None,
            segment_render_plan_path=None,
            segment_video_paths=[],
        )
        audio_result = AudioOrchestrationResult(
            beats=[],
            timeline=TimelineSpec(total_duration_seconds=3.0),
            concatenated_audio_path="out/audio_track.mp3",
            concatenated_subtitle_path="out/subtitles.srt",
            bgm_path="out/bgm.mp3",
        )

        with patch(
            "manim_agent.pipeline_phases345.build_final_video",
            new_callable=AsyncMock,
            return_value="out/final.mp4",
        ) as mock_build:
            result = await run_phase5_mux(
                dispatcher=dispatcher,
                video_output="media/out.mp4",
                audio_result=audio_result,
                output_path="out/final.mp4",
                po=po,
                bgm_volume=0.2,
                intro_outro=False,
                event_callback=None,
            )

        assert result == "out/final.mp4"
        assert po.final_video_output == "out/final.mp4"
        mock_build.assert_awaited_once_with(
            video_path="media/out.mp4",
            audio_path="out/audio_track.mp3",
            subtitle_path="out/subtitles.srt",
            output_path="out/final.mp4",
            bgm_path="out/bgm.mp3",
            bgm_volume=0.2,
        )

    @pytest.mark.asyncio
    async def test_run_phase5_mux_extracts_segment_videos_when_plan_exists(self, tmp_path):
        dispatcher = _MessageDispatcher(verbose=False, output_cwd=str(tmp_path))
        po = SimpleNamespace(
            final_video_output=None,
            intro_video_path=None,
            outro_video_path=None,
            segment_render_plan_path="out/segment_render_plan.json",
            segment_video_paths=[],
        )
        audio_result = AudioOrchestrationResult(
            beats=[],
            timeline=TimelineSpec(total_duration_seconds=3.0),
            concatenated_audio_path="out/audio_track.mp3",
            concatenated_subtitle_path=None,
            bgm_path=None,
        )
        plan = SegmentRenderPlan(total_duration_seconds=3.0, segments=[])

        with (
            patch(
                "manim_agent.pipeline_phases345.build_final_video",
                new_callable=AsyncMock,
                return_value="out/final.mp4",
            ),
            patch("manim_agent.pipeline_phases345.read_segment_render_plan", return_value=plan),
            patch(
                "manim_agent.pipeline_phases345.extract_video_segments",
                new_callable=AsyncMock,
                return_value=["out/segments/beat_001.mp4"],
            ) as mock_extract,
        ):
            result = await run_phase5_mux(
                dispatcher=dispatcher,
                video_output="media/out.mp4",
                audio_result=audio_result,
                output_path="out/final.mp4",
                po=po,
                bgm_volume=0.2,
                intro_outro=False,
                event_callback=None,
            )

        assert result == "out/final.mp4"
        assert po.segment_video_paths == ["out/segments/beat_001.mp4"]
        mock_extract.assert_awaited_once_with("out/final.mp4", plan)

    @pytest.mark.asyncio
    async def test_run_phase5_mux_prefers_existing_segment_videos(self, tmp_path):
        dispatcher = _MessageDispatcher(verbose=False, output_cwd=str(tmp_path))
        segment_a = tmp_path / "segments" / "beat_001.mp4"
        segment_b = tmp_path / "segments" / "beat_002.mp4"
        segment_a.parent.mkdir(parents=True, exist_ok=True)
        segment_a.write_bytes(b"a")
        segment_b.write_bytes(b"b")
        po = SimpleNamespace(
            final_video_output=None,
            intro_video_path=None,
            outro_video_path=None,
            segment_render_plan_path="out/segment_render_plan.json",
            segment_video_paths=[str(segment_a), str(segment_b)],
        )
        audio_result = AudioOrchestrationResult(
            beats=[],
            timeline=TimelineSpec(total_duration_seconds=3.0),
            concatenated_audio_path="out/audio_track.mp3",
            concatenated_subtitle_path=None,
            bgm_path=None,
        )

        with (
            patch(
                "manim_agent.pipeline_phases345.concat_videos",
                new_callable=AsyncMock,
                return_value="out/segment_visual_track.mp4",
            ) as mock_concat,
            patch(
                "manim_agent.pipeline_phases345.build_final_video",
                new_callable=AsyncMock,
                return_value="out/final.mp4",
            ) as mock_build,
            patch("manim_agent.pipeline_phases345.read_segment_render_plan") as mock_read_plan,
            patch(
                "manim_agent.pipeline_phases345.extract_video_segments",
                new_callable=AsyncMock,
            ) as mock_extract,
        ):
            result = await run_phase5_mux(
                dispatcher=dispatcher,
                video_output="media/out.mp4",
                audio_result=audio_result,
                output_path="out/final.mp4",
                po=po,
                bgm_volume=0.2,
                intro_outro=False,
                event_callback=None,
            )

        assert result == "out/final.mp4"
        mock_concat.assert_awaited_once()
        mock_build.assert_awaited_once_with(
            video_path="out/segment_visual_track.mp4",
            audio_path="out/audio_track.mp3",
            subtitle_path=None,
            output_path="out/final.mp4",
            bgm_path=None,
            bgm_volume=0.2,
        )
        mock_read_plan.assert_not_called()
        mock_extract.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_run_phase5_mux_falls_back_when_segment_video_missing(self, tmp_path):
        dispatcher = _MessageDispatcher(verbose=False, output_cwd=str(tmp_path))
        po = SimpleNamespace(
            final_video_output=None,
            intro_video_path=None,
            outro_video_path=None,
            segment_render_plan_path=None,
            segment_video_paths=[str(tmp_path / "segments" / "missing.mp4")],
        )
        audio_result = AudioOrchestrationResult(
            beats=[],
            timeline=TimelineSpec(total_duration_seconds=3.0),
            concatenated_audio_path="out/audio_track.mp3",
            concatenated_subtitle_path=None,
            bgm_path=None,
        )

        with (
            patch(
                "manim_agent.pipeline_phases345.concat_videos",
                new_callable=AsyncMock,
            ) as mock_concat,
            patch(
                "manim_agent.pipeline_phases345.build_final_video",
                new_callable=AsyncMock,
                return_value="out/final.mp4",
            ) as mock_build,
        ):
            result = await run_phase5_mux(
                dispatcher=dispatcher,
                video_output="media/out.mp4",
                audio_result=audio_result,
                output_path="out/final.mp4",
                po=po,
                bgm_volume=0.2,
                intro_outro=False,
                event_callback=None,
            )

        assert result == "out/final.mp4"
        mock_concat.assert_not_awaited()
        mock_build.assert_awaited_once_with(
            video_path="media/out.mp4",
            audio_path="out/audio_track.mp3",
            subtitle_path=None,
            output_path="out/final.mp4",
            bgm_path=None,
            bgm_volume=0.2,
        )
