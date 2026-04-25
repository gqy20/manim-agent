"""Focused backend helper tests without external DB dependency."""

from __future__ import annotations

import datetime
import json

from backend.routes import _format_exception_message, _task_update_kwargs
from backend.sse_manager import SSESubscriptionManager
from backend.task_store import TaskStore


class TestTaskStoreResponseNormalization:
    def test_to_response_normalizes_db_native_types(self):
        store = TaskStore()
        task = {
            "id": "task-1",
            "user_text": "test",
            "status": "completed",
            "created_at": datetime.datetime(2026, 4, 11, 13, 0, 0, tzinfo=datetime.UTC),
            "completed_at": datetime.datetime(2026, 4, 11, 13, 5, 0, tzinfo=datetime.UTC),
            "video_path": "/out.mp4",
            "error": None,
            "options": '{"voice_id":"female-tianmei","quality":"high"}',
            "pipeline_output": (
                '{"video_output":"/out.mp4","scene_file":"scene.py",'
                '"phase1_planning":{"build_spec":{"mode":"teaching-animation"}}}'
            ),
        }

        response = store.to_response(task)

        assert response.created_at == "2026-04-11T13:00:00+00:00"
        assert response.completed_at == "2026-04-11T13:05:00+00:00"
        assert response.options["voice_id"] == "female-tianmei"
        assert response.pipeline_output is not None
        assert response.pipeline_output.video_output == "/out.mp4"
        assert response.pipeline_output.scene_file == "scene.py"
        assert response.pipeline_output.phase1_planning is not None
        assert (
            response.pipeline_output.phase1_planning["build_spec"]["mode"]
            == "teaching-animation"
        )

    def test_to_response_keeps_pipeline_output_none_when_missing(self):
        store = TaskStore()
        task = {
            "id": "task-2",
            "user_text": "test",
            "status": "pending",
            "created_at": "2026-04-11T13:00:00+00:00",
            "completed_at": None,
            "video_path": None,
            "error": None,
            "options": {"quality": "high"},
            "pipeline_output": None,
        }

        response = store.to_response(task)

        assert response.pipeline_output is None
        assert response.options == {"quality": "high"}


class TestExceptionFormatting:
    def test_chained_exception_includes_cause(self):
        try:
            raise RuntimeError("Failed to start Claude Code") from OSError(
                "The system cannot find the file specified",
            )
        except RuntimeError as exc:
            message = _format_exception_message(exc)

        assert "RuntimeError" in message
        assert "OSError" in message
        assert "The system cannot find the file specified" in message

    def test_empty_exception_message_still_includes_type_name(self):
        message = _format_exception_message(RuntimeError())
        assert "RuntimeError" in message


class TestTaskUpdateKwargs:
    def test_omits_missing_pipeline_output_to_preserve_existing_phase1_data(self):
        assert _task_update_kwargs(error="phase2 failed", pipeline_output=None) == {
            "error": "phase2 failed",
        }

    def test_includes_pipeline_output_when_available(self):
        pipeline_output = {"phase1_planning": {"build_spec": {"mode": "proof"}}}

        assert _task_update_kwargs(
            video_path="/out.mp4",
            pipeline_output=pipeline_output,
        ) == {
            "video_path": "/out.mp4",
            "pipeline_output": pipeline_output,
        }


class TestSSEManager:
    def test_subscribe_push_done(self):
        mgr = SSESubscriptionManager()
        q = mgr.subscribe("t1")

        mgr.push("t1", "hello")
        mgr.push("t1", "world")
        mgr.done("t1")

        assert json.loads(q.get_nowait())["data"] == "hello"
        assert json.loads(q.get_nowait())["data"] == "world"
        assert q.get_nowait() is None

    def test_replay_buffer_to_new_subscriber(self):
        mgr = SSESubscriptionManager()
        mgr.push("t2", "buffered-1")
        mgr.push("t2", "buffered-2")

        q = mgr.subscribe("t2", replay=True)

        assert json.loads(q.get_nowait())["data"] == "buffered-1"
        assert json.loads(q.get_nowait())["data"] == "buffered-2"

    def test_multiple_subscribers_receive_same_events(self):
        mgr = SSESubscriptionManager()
        q1 = mgr.subscribe("t3")
        q2 = mgr.subscribe("t3")

        mgr.push("t3", "event-a")
        mgr.push("t3", "event-b")

        assert json.loads(q1.get_nowait())["data"] == "event-a"
        assert json.loads(q1.get_nowait())["data"] == "event-b"
        assert json.loads(q2.get_nowait())["data"] == "event-a"
        assert json.loads(q2.get_nowait())["data"] == "event-b"

    def test_unsubscribe_stops_live_delivery(self):
        mgr = SSESubscriptionManager()
        q = mgr.subscribe("t4")
        mgr.unsubscribe("t4", q)

        mgr.push("t4", "live")

        assert q.empty()
        assert json.loads(mgr.get_buffer("t4")[0])["data"] == "live"

    def test_cleanup(self):
        mgr = SSESubscriptionManager()
        mgr.subscribe("t5")
        mgr.push("t5", "x")
        assert mgr.get_buffer("t5")

        mgr.cleanup("t5")
        assert mgr.get_buffer("t5") == []
        assert "t5" not in mgr._subscribers
