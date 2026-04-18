from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from backend.models import TaskStatus
from backend.routes import set_store, terminate_task
from backend.task_runtime import TaskRuntime, clear_task_runtimes, register_task_runtime


class _FakeRuntime:
    def __init__(self) -> None:
        self.terminate_calls = 0

    def request_termination(self) -> bool:
        self.terminate_calls += 1
        return True


@pytest.mark.asyncio
async def test_terminate_task_rejects_missing_task() -> None:
    set_store(SimpleNamespace(get=AsyncMock(return_value=None)))
    clear_task_runtimes()

    with pytest.raises(HTTPException, match="Task not found"):
        await terminate_task("missing-task")


@pytest.mark.asyncio
async def test_terminate_task_stops_running_task() -> None:
    task = {
        "id": "task-1",
        "user_text": "demo",
        "status": TaskStatus.RUNNING.value,
        "created_at": "2026-01-01T00:00:00+00:00",
        "completed_at": None,
        "video_path": None,
        "error": None,
        "options": {},
        "pipeline_output": None,
    }
    store = SimpleNamespace(
        get=AsyncMock(side_effect=[task, {**task, "status": TaskStatus.STOPPED.value, "error": "Task terminated by user."}]),
        update_status=AsyncMock(),
        to_response=lambda item: item,
    )
    set_store(store)
    runtime = _FakeRuntime()
    clear_task_runtimes()
    register_task_runtime("task-1", runtime)

    response = await terminate_task("task-1")

    assert response["status"] == TaskStatus.STOPPED.value
    assert runtime.terminate_calls == 1
    store.update_status.assert_awaited_once_with(
        "task-1",
        TaskStatus.STOPPED,
        error="Task terminated by user.",
    )
    clear_task_runtimes()


@pytest.mark.asyncio
async def test_terminate_task_is_idempotent_for_terminal_tasks() -> None:
    task = {
        "id": "task-2",
        "user_text": "demo",
        "status": TaskStatus.STOPPED.value,
        "created_at": "2026-01-01T00:00:00+00:00",
        "completed_at": "2026-01-01T00:01:00+00:00",
        "video_path": None,
        "error": "Task terminated by user.",
        "options": {},
        "pipeline_output": None,
    }
    store = SimpleNamespace(
        get=AsyncMock(return_value=task),
        update_status=AsyncMock(),
        to_response=lambda item: item,
    )
    set_store(store)
    clear_task_runtimes()

    response = await terminate_task("task-2")

    assert response["status"] == TaskStatus.STOPPED.value
    store.update_status.assert_not_awaited()


def test_task_runtime_marks_cancel_requested_for_inline_tasks() -> None:
    runtime = TaskRuntime(task_id="task-3", mode="inline")
    async_task = SimpleNamespace(cancel=Mock())
    runtime.set_async_task(async_task)

    terminated = runtime.request_termination()

    assert terminated is True
    assert runtime.cancel_requested is True
    async_task.cancel.assert_called_once_with()
