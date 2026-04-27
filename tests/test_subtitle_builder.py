from manim_agent.beat_schema import BeatSpec, TimelineSpec
from manim_agent.subtitle_builder import write_timeline_srt


def test_write_timeline_srt_uses_beat_boundaries(tmp_path):
    timeline = TimelineSpec(
        total_duration_seconds=5.5,
        beats=[
            BeatSpec(
                id="beat_001",
                title="Opening",
                narration_text="首先看开场。",
                start_seconds=0.0,
                end_seconds=2.0,
            ),
            BeatSpec(
                id="beat_002",
                title="Main",
                narration_text="接着解释核心关系。",
                start_seconds=2.0,
                end_seconds=5.5,
            ),
        ],
    )

    path = write_timeline_srt(timeline, str(tmp_path / "timeline_subtitles.srt"))

    assert path == str(tmp_path / "timeline_subtitles.srt")
    text = (tmp_path / "timeline_subtitles.srt").read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:02,000" in text
    assert "00:00:02,000 --> 00:00:05,500" in text
    assert "首先看开场。" in text
    assert "接着解释核心关系。" in text
