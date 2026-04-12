import json
from pathlib import Path

from ._test_main_dispatcher_helpers import (
    _MessageDispatcher,
    _make_result_message,
    TaskNotificationMessage,
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

    def test_task_notification_sets_video_output(self):
        d = _MessageDispatcher(verbose=False)
        d.dispatch(
            TaskNotificationMessage(
                subtype="task_notification",
                task_id="t1",
                status="completed",
                output_file="/sdk/out.mp4",
                summary="done",
                uuid="u1",
                session_id="s1",
                data={},
            )
        )
        assert d.get_video_output() == str(Path("/sdk/out.mp4").resolve())

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
        assert po.video_output == str(Path("/task/out.mp4").resolve())
        assert po.scene_file.endswith("scene.py")
        assert po.scene_class == "GeneratedScene"
        assert po.narration == "这是合并后的中文解说。"
        assert po.duration_seconds == 8
