import json
from pathlib import Path

import pytest

from ._test_main_dispatcher_helpers import (
    TaskNotificationMessage,
    _make_result_message,
    _MessageDispatcher,
)


class TestDispatcherPipelineOutput:
    def test_get_pipeline_output_returns_model_from_structured_output(self):
        d = _MessageDispatcher(verbose=False)
        d.dispatch(
            _make_result_message(
                num_turns=1,
                **{
                    "structured_output": {
                        "video_output": "/media/out.mp4",
                        "scene_file": "scene.py",
                        "scene_class": "MyScene",
                        "duration_seconds": 25,
                        "render_mode": "segments",
                        "segment_render_complete": True,
                        "segment_video_paths": ["/media/segments/beat_001.mp4"],
                    }
                },
            )
        )

        po = d.get_pipeline_output()
        assert po is not None
        assert po.video_output == str(Path("/media/out.mp4").resolve())
        assert po.scene_file == str(Path("scene.py").resolve())
        assert po.scene_class == "MyScene"
        assert po.duration_seconds == 25
        assert po.render_mode == "segments"
        assert po.segment_render_complete is True
        assert po.segment_video_paths == [str(Path("/media/segments/beat_001.mp4").resolve())]

    def test_get_pipeline_output_accepts_segment_mode_without_video_output(self):
        d = _MessageDispatcher(verbose=False)
        d.dispatch(
            _make_result_message(
                num_turns=1,
                **{
                    "structured_output": {
                        "video_output": None,
                        "render_mode": "segments",
                        "segment_render_complete": True,
                        "segment_video_paths": ["/media/segments/beat_001.mp4"],
                        "implemented_beats": ["Opening"],
                        "deviations_from_plan": [],
                        "beat_to_narration_map": [],
                        "run_tool_stats": {},
                        "review_blocking_issues": [],
                        "review_suggested_edits": [],
                        "review_frame_paths": [],
                    }
                },
            )
        )

        po = d.get_pipeline_output()
        assert po is not None
        assert po.video_output is None
        assert po.render_mode == "segments"
        assert po.segment_render_complete is True
        assert po.segment_video_paths == [str(Path("/media/segments/beat_001.mp4").resolve())]

    def test_phase1_expected_output_only_parses_phase1_schema(self):
        d = _MessageDispatcher(verbose=False, expected_output="phase1_planning")
        d.dispatch(
            _make_result_message(
                num_turns=1,
                result=json.dumps({"video_output": "/should/not/parse.mp4"}),
                structured_output={
                    "build_spec": {
                        "mode": "teaching-animation",
                        "learning_goal": "Explain a key idea.",
                        "audience": "Beginners",
                        "target_duration_seconds": 60,
                        "beats": [
                            {
                                "id": "beat_001_intro",
                                "title": "Intro",
                                "visual_goal": "Show title card.",
                                "narration_intent": "Set up context.",
                                "target_duration_seconds": 12,
                                "required_elements": ["title"],
                                "segment_required": True,
                            },
                        ],
                    },
                },
            )
        )

        assert d.get_scene_plan_output() is not None
        assert d._structured_output_candidate is None
        assert d.pipeline_output is None

    def test_pipeline_expected_output_skips_phase1_schema_parse(self):
        d = _MessageDispatcher(verbose=False, expected_output="pipeline_output")
        d.dispatch(
            _make_result_message(
                num_turns=1,
                structured_output={
                    "video_output": "/media/out.mp4",
                    "scene_file": "scene.py",
                    "scene_class": "MyScene",
                },
            )
        )

        assert d.get_pipeline_output() is not None
        assert d.get_scene_plan_output() is None

    def test_phase2_expected_output_only_parses_phase2_schema(self):
        d = _MessageDispatcher(verbose=False, expected_output="phase2_implementation")
        d.dispatch(
            _make_result_message(
                num_turns=1,
                result=json.dumps({"video_output": "/should/not/parse.mp4"}),
                structured_output={
                    "scene_file": "scene.py",
                    "scene_class": "GeneratedScene",
                    "video_output": "media/out.mp4",
                    "narration": "大家好，今天我们讲解这个动画的核心过程。",
                    "implemented_beats": ["Intro"],
                    "build_summary": "Built the intro beat.",
                    "deviations_from_plan": [],
                },
            )
        )

        phase2_output = d.get_phase2_implementation_output()
        assert phase2_output is not None
        assert phase2_output.video_output == "media/out.mp4"
        assert d.pipeline_output is None
        assert d._result_output_candidate is None

    def test_phase2_script_draft_expected_output_only_parses_draft_schema(self):
        d = _MessageDispatcher(verbose=False, expected_output="phase2_script_draft")
        d.dispatch(
            _make_result_message(
                num_turns=1,
                result=json.dumps({"video_output": "/should/not/parse.mp4"}),
                structured_output={
                    "scene_file": "scene.py",
                    "scene_class": "GeneratedScene",
                    "implemented_beats": ["Intro"],
                    "build_summary": "Built the beat-first script draft.",
                    "beat_timing_seconds": {"Intro": 6.0},
                    "estimated_duration_seconds": 6.0,
                    "deviations_from_plan": [],
                    "source_code": (
                        "from manim import *\n\nclass GeneratedScene(Scene):\n    pass\n"
                    ),
                },
            )
        )

        draft_output = d.get_phase2_script_draft_output()
        assert draft_output is not None
        assert draft_output.scene_file == "scene.py"
        assert d.pipeline_output is None
        assert d.get_phase2_implementation_output() is None

    def test_get_pipeline_output_none_when_no_result_signal(self):
        d = _MessageDispatcher(verbose=False)
        d.dispatch(_make_result_message(num_turns=1))
        assert d.get_pipeline_output() is None

    def test_get_pipeline_output_from_result_json_fallback(self):
        d = _MessageDispatcher(verbose=False)
        d.dispatch(
            _make_result_message(
                num_turns=1,
                result=json.dumps(
                    {
                        "video_output": "/result/out.mp4",
                        "scene_file": "scene.py",
                        "narration": "hello",
                    }
                ),
            )
        )

        po = d.get_pipeline_output()
        assert po is not None
        assert po.video_output == str(Path("/result/out.mp4").resolve())
        assert po.scene_file.endswith("scene.py")
        assert po.narration == "hello"

    def test_task_notification_sets_video_output_for_existing_file(self, tmp_path: Path):
        video_path = tmp_path / "sdk-out.mp4"
        video_path.write_bytes(b"fake-mp4")
        d = _MessageDispatcher(verbose=False)
        d.dispatch(
            TaskNotificationMessage(
                subtype="task_notification",
                task_id="t1",
                status="completed",
                output_file=str(video_path),
                summary="done",
                uuid="u1",
                session_id="s1",
                data={},
            )
        )
        assert d.get_video_output() == str(video_path.resolve())

    def test_get_pipeline_output_falls_back_to_rendered_mp4_after_completion(self, tmp_path: Path):
        video_path = tmp_path / "media" / "videos" / "scene" / "1080p60" / "demo.mp4"
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(b"fake-mp4")

        d = _MessageDispatcher(verbose=False, output_cwd=str(tmp_path))
        d.dispatch(
            TaskNotificationMessage(
                subtype="task_notification",
                task_id="t1",
                status="completed",
                output_file=None,
                summary="done",
                uuid="u1",
                session_id="s1",
                data={},
            )
        )

        po = d.get_pipeline_output()
        assert po is not None
        assert po.video_output == str(video_path.resolve())

    def test_get_pipeline_output_falls_back_to_segment_videos_after_completion(
        self, tmp_path: Path
    ):
        segment_a = tmp_path / "segments" / "beat_001.mp4"
        segment_b = tmp_path / "segments" / "beat_002.mp4"
        segment_a.parent.mkdir(parents=True, exist_ok=True)
        segment_a.write_bytes(b"fake-a")
        segment_b.write_bytes(b"fake-b")

        d = _MessageDispatcher(verbose=False, output_cwd=str(tmp_path))
        d.dispatch(
            TaskNotificationMessage(
                subtype="task_notification",
                task_id="t1",
                status="completed",
                output_file=None,
                summary="done",
                uuid="u1",
                session_id="s1",
                data={},
            )
        )

        po = d.get_pipeline_output()
        assert po is not None
        assert po.video_output is None
        assert po.render_mode == "segments"
        assert po.segment_render_complete is True
        assert po.segment_video_paths == [str(segment_a.resolve()), str(segment_b.resolve())]

    def test_structured_output_merges_into_existing_pipeline_output(self):
        d = _MessageDispatcher(verbose=False)
        d.dispatch(
            TaskNotificationMessage(
                subtype="task_notification",
                task_id="t1",
                status="completed",
                output_file="/task/out.mp4",
                summary="render done",
                uuid="u1",
                session_id="s1",
                data={},
            )
        )
        d.dispatch(
            _make_result_message(
                num_turns=1,
                **{
                    "structured_output": {
                        "video_output": "/structured/out.mp4",
                        "scene_file": "scene.py",
                        "scene_class": "GeneratedScene",
                        "narration": "这是合并后的中文解说。",
                        "duration_seconds": 8,
                    }
                },
            )
        )

        po = d.get_pipeline_output()
        assert po is not None
        assert po.video_output == str(Path("/structured/out.mp4").resolve())
        assert po.scene_file.endswith("scene.py")
        assert po.scene_class == "GeneratedScene"
        assert po.narration == "这是合并后的中文解说。"
        assert po.duration_seconds == 8


def test_persistable_output_includes_phase1_planning():
    """From former test_dispatcher_pipeline_output_persistence.py."""
    d = _MessageDispatcher(verbose=False, expected_output="phase1_planning")
    d.dispatch(
        _make_result_message(
            num_turns=1,
            structured_output={
                "build_spec": {
                    "mode": "teaching-animation",
                    "learning_goal": "Explain a key idea.",
                    "audience": "Beginner learners",
                    "target_duration_seconds": 60,
                    "beats": [
                        {
                            "id": "beat_001_intro",
                            "title": "Intro",
                            "visual_goal": "Show title card.",
                            "narration_intent": "Set up context.",
                            "target_duration_seconds": 12,
                            "required_elements": ["title"],
                            "segment_required": True,
                        },
                    ],
                },
            },
        )
    )
    payload = d.get_persistable_pipeline_output()

    assert payload is not None
    assert payload["phase1_planning"] is not None
    assert payload["phase1_planning"]["build_spec"]["mode"] == "teaching-animation"


@pytest.mark.asyncio
async def test_dispatcher_ref_is_available_when_phase1_fails(tmp_path):
    """From former test_pipeline_dispatcher_ref.py."""
    from unittest.mock import AsyncMock, patch

    from manim_agent import pipeline

    dispatcher_ref = []

    with patch(
        "manim_agent.pipeline.run_phase1_planning",
        new_callable=AsyncMock,
        side_effect=RuntimeError("phase1 boom"),
    ):
        with pytest.raises(RuntimeError, match="phase1 boom"):
            await pipeline.run_pipeline(
                user_text="test",
                output_path=str(tmp_path / "final.mp4"),
                no_tts=True,
                cwd=str(tmp_path),
                _dispatcher_ref=dispatcher_ref,
            )

    assert len(dispatcher_ref) == 1
    diagnostics = dispatcher_ref[0].get_phase1_failure_diagnostics()
    assert diagnostics["raw_structured_output_present"] is False
    assert diagnostics["raw_structured_output_type"] is None
