from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from manim_agent.beat_schema import BeatSpec, TimelineSpec
from manim_agent.segment_renderer import (
    SegmentRenderPlan,
    build_segment_render_plan,
    discover_segment_video_paths,
    extract_video_segments,
    write_segment_render_plan,
)


class TestBuildSegmentRenderPlan:
    def test_builds_one_segment_per_timeline_beat(self, tmp_path):
        timeline = TimelineSpec(
            beats=[
                BeatSpec(
                    id="beat_001",
                    title="Opening",
                    start_seconds=0.0,
                    end_seconds=1.5,
                    actual_audio_duration_seconds=1.5,
                ),
                BeatSpec(
                    id="beat_002",
                    title="Main idea",
                    start_seconds=1.5,
                    end_seconds=4.0,
                    actual_audio_duration_seconds=2.5,
                ),
            ],
            total_duration_seconds=4.0,
        )

        plan = build_segment_render_plan(
            timeline=timeline,
            output_dir=str(tmp_path),
            scene_file="scene.py",
            scene_class="GeneratedScene",
        )

        assert isinstance(plan, SegmentRenderPlan)
        assert len(plan.segments) == 2
        assert plan.segments[0].output_path.endswith("segments\\beat_001.mp4")
        assert plan.segments[1].target_duration_seconds == 2.5
        assert plan.total_duration_seconds == 4.0

    def test_skips_zero_duration_beats(self, tmp_path):
        timeline = TimelineSpec(
            beats=[
                BeatSpec(id="beat_001", title="Empty", start_seconds=0.0, end_seconds=0.0),
                BeatSpec(
                    id="beat_002",
                    title="Actual",
                    start_seconds=0.0,
                    end_seconds=1.0,
                    actual_audio_duration_seconds=1.0,
                ),
            ],
            total_duration_seconds=1.0,
        )

        plan = build_segment_render_plan(
            timeline=timeline,
            output_dir=str(tmp_path),
            scene_file="scene.py",
            scene_class="GeneratedScene",
        )

        assert [segment.beat_id for segment in plan.segments] == ["beat_002"]


class TestWriteSegmentRenderPlan:
    def test_persists_render_plan_json(self, tmp_path):
        timeline = TimelineSpec(
            beats=[
                BeatSpec(
                    id="beat_001",
                    title="Opening",
                    start_seconds=0.0,
                    end_seconds=1.0,
                    actual_audio_duration_seconds=1.0,
                )
            ],
            total_duration_seconds=1.0,
        )
        plan = build_segment_render_plan(
            timeline=timeline,
            output_dir=str(tmp_path),
            scene_file="scene.py",
            scene_class="GeneratedScene",
        )

        output_path = write_segment_render_plan(
            plan,
            str(tmp_path / "segment_render_plan.json"),
        )

        assert Path(output_path).exists()
        assert '"beat_id": "beat_001"' in Path(output_path).read_text(encoding="utf-8")


class TestDiscoverSegmentVideoPaths:
    def test_prefers_existing_expected_paths_in_given_order(self, tmp_path):
        first = tmp_path / "segments" / "beat_002.mp4"
        second = tmp_path / "segments" / "beat_001.mp4"
        first.parent.mkdir(parents=True, exist_ok=True)
        first.write_bytes(b"two")
        second.write_bytes(b"one")

        discovered = discover_segment_video_paths(
            output_dir=str(tmp_path),
            expected_paths=[str(first), str(second)],
        )

        assert discovered == [str(first), str(second)]

    def test_scans_segment_directory_when_expected_paths_missing(self, tmp_path):
        first = tmp_path / "segments" / "beat_002.mp4"
        second = tmp_path / "segments" / "beat_001.mp4"
        first.parent.mkdir(parents=True, exist_ok=True)
        first.write_bytes(b"two")
        second.write_bytes(b"one")

        discovered = discover_segment_video_paths(output_dir=str(tmp_path))

        assert discovered == [str(second), str(first)]


class TestExtractVideoSegments:
    @pytest.mark.asyncio
    async def test_extracts_one_ffmpeg_clip_per_segment(self, tmp_path):
        source_video = tmp_path / "final.mp4"
        source_video.write_bytes(b"fake")
        plan = SegmentRenderPlan(
            scene_file="scene.py",
            scene_class="GeneratedScene",
            total_duration_seconds=3.0,
            segments=[
                build_segment_render_plan(
                    timeline=TimelineSpec(
                        beats=[
                            BeatSpec(
                                id="beat_001",
                                title="Opening",
                                start_seconds=0.0,
                                end_seconds=1.0,
                                actual_audio_duration_seconds=1.0,
                            )
                        ],
                        total_duration_seconds=1.0,
                    ),
                    output_dir=str(tmp_path),
                    scene_file="scene.py",
                    scene_class="GeneratedScene",
                ).segments[0],
                build_segment_render_plan(
                    timeline=TimelineSpec(
                        beats=[
                            BeatSpec(
                                id="beat_002",
                                title="Main",
                                start_seconds=1.0,
                                end_seconds=3.0,
                                actual_audio_duration_seconds=2.0,
                            )
                        ],
                        total_duration_seconds=2.0,
                    ),
                    output_dir=str(tmp_path),
                    scene_file="scene.py",
                    scene_class="GeneratedScene",
                ).segments[0],
            ],
        )

        proc = AsyncMock()
        proc.returncode = 0
        proc.communicate.return_value = (b"", b"")

        with patch(
            "manim_agent.segment_renderer.asyncio.create_subprocess_exec",
            return_value=proc,
        ) as mock_exec:
            outputs = await extract_video_segments(str(source_video), plan)

        assert len(outputs) == 2
        assert outputs[0].endswith("segments\\beat_001.mp4")
        assert outputs[1].endswith("segments\\beat_002.mp4")
        assert mock_exec.await_count == 2

    @pytest.mark.asyncio
    async def test_raises_when_source_video_missing(self, tmp_path):
        plan = SegmentRenderPlan(total_duration_seconds=0.0, segments=[])

        with pytest.raises(FileNotFoundError, match="Source video not found"):
            await extract_video_segments(str(tmp_path / "missing.mp4"), plan)
