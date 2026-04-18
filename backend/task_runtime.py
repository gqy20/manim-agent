"""Runtime registry for active backend tasks and cooperative termination."""

from __future__ import annotations

import asyncio
import ctypes
import threading
from dataclasses import dataclass, field
from typing import Any


class TaskTerminationRequested(BaseException):
    """Raised inside a worker when a user requests termination."""


def _raise_async_exception(thread_id: int, exc_type: type[BaseException]) -> bool:
    """Inject *exc_type* into a running Python thread."""
    result = ctypes.pythonapi.PyThreadState_SetAsyncExc(
        ctypes.c_ulong(thread_id),
        ctypes.py_object(exc_type),
    )
    if result == 0:
        return False
    if result > 1:
        ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_ulong(thread_id), None)
        return False
    return True


@dataclass(slots=True)
class TaskRuntime:
    task_id: str
    mode: str
    async_task: asyncio.Task[Any] | None = None
    thread_id: int | None = None
    cancel_requested: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def set_async_task(self, task: asyncio.Task[Any]) -> None:
        with self._lock:
            self.async_task = task

    def set_thread_id(self, thread_id: int) -> None:
        with self._lock:
            self.thread_id = thread_id

    def request_termination(self) -> bool:
        with self._lock:
            self.cancel_requested = True
            if self.async_task is not None:
                self.async_task.cancel()
                return True
            if self.thread_id is not None:
                return _raise_async_exception(self.thread_id, TaskTerminationRequested)
        return False


_TASK_RUNTIMES: dict[str, TaskRuntime] = {}
_TASK_RUNTIMES_LOCK = threading.Lock()


def register_task_runtime(task_id: str, runtime: TaskRuntime) -> TaskRuntime:
    with _TASK_RUNTIMES_LOCK:
        _TASK_RUNTIMES[task_id] = runtime
    return runtime


def get_task_runtime(task_id: str) -> TaskRuntime | None:
    with _TASK_RUNTIMES_LOCK:
        return _TASK_RUNTIMES.get(task_id)


def unregister_task_runtime(task_id: str) -> None:
    with _TASK_RUNTIMES_LOCK:
        _TASK_RUNTIMES.pop(task_id, None)


def clear_task_runtimes() -> None:
    with _TASK_RUNTIMES_LOCK:
        _TASK_RUNTIMES.clear()
