from manim_agent.beat_schema import BeatSpec
from manim_agent.timeline_builder import finalize_timeline


class TestFinalizeTimeline:
    def test_accumulates_beat_boundaries(self):
        beats = [
            BeatSpec(id="beat_1", title="Opening", actual_audio_duration_seconds=1.25),
            BeatSpec(id="beat_2", title="Middle", actual_audio_duration_seconds=2.5),
            BeatSpec(id="beat_3", title="Ending", actual_audio_duration_seconds=0.75),
        ]

        timeline = finalize_timeline(beats)

        assert timeline.total_duration_seconds == 4.5
        assert [beat.start_seconds for beat in timeline.beats] == [0.0, 1.25, 3.75]
        assert [beat.end_seconds for beat in timeline.beats] == [1.25, 3.75, 4.5]

    def test_handles_missing_durations_as_zero(self):
        beats = [
            BeatSpec(id="beat_1", title="Only", actual_audio_duration_seconds=None),
        ]

        timeline = finalize_timeline(beats)

        assert timeline.total_duration_seconds == 0.0
        assert timeline.beats[0].start_seconds == 0.0
        assert timeline.beats[0].end_seconds == 0.0

    def test_prefers_visual_target_duration_over_audio_duration(self):
        beats = [
            BeatSpec(
                id="beat_1",
                title="Opening",
                target_duration_seconds=6.0,
                actual_audio_duration_seconds=4.0,
            ),
            BeatSpec(
                id="beat_2",
                title="Middle",
                target_duration_seconds=3.0,
                actual_audio_duration_seconds=5.0,
            ),
        ]

        timeline = finalize_timeline(beats)

        assert timeline.total_duration_seconds == 9.0
        assert [beat.start_seconds for beat in timeline.beats] == [0.0, 6.0]
        assert [beat.end_seconds for beat in timeline.beats] == [6.0, 9.0]
