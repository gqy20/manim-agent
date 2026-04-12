from __future__ import annotations

from backend.routes import _terminal_status_payload
from backend.models import TaskStatus


def test_terminal_status_payload_includes_final_artifacts() -> None:
    task = {
        "status": TaskStatus.COMPLETED.value,
        "error": None,
        "video_path": "https://example.com/final.mp4",
        "pipeline_output": {"narration": "方圆相生"},
    }

    payload = _terminal_status_payload(task)

    assert payload == {
        "task_status": TaskStatus.COMPLETED.value,
        "phase": "done",
        "message": "Pipeline completed",
        "video_path": "https://example.com/final.mp4",
        "pipeline_output": {"narration": "方圆相生"},
    }
