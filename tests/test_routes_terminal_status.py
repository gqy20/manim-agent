from __future__ import annotations

from backend.models import TaskStatus
from backend.routes import _terminal_status_payload


def test_terminal_status_payload_includes_final_artifacts() -> None:
    task = {
        "status": TaskStatus.COMPLETED.value,
        "error": None,
        "video_path": "https://example.com/final.mp4",
        "pipeline_output": {"narration": "demo"},
    }

    payload = _terminal_status_payload(task)

    assert payload == {
        "task_status": TaskStatus.COMPLETED.value,
        "phase": "done",
        "message": "Pipeline completed",
        "video_path": "https://example.com/final.mp4",
        "pipeline_output": {"narration": "demo"},
    }


def test_terminal_status_payload_marks_stopped_tasks() -> None:
    task = {
        "status": TaskStatus.STOPPED.value,
        "error": "Task terminated by user.",
        "video_path": None,
        "pipeline_output": None,
    }

    payload = _terminal_status_payload(task)

    assert payload == {
        "task_status": TaskStatus.STOPPED.value,
        "phase": None,
        "message": "Task terminated by user.",
        "video_path": None,
        "pipeline_output": None,
    }
