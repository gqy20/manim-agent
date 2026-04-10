"""SSE subscription manager: per-task asyncio.Queue for real-time log streaming."""

from __future__ import annotations

import asyncio
from typing import Any


class SSESubscriptionManager:
    """Manages per-task asyncio.Queue subscriptions for SSE streaming.

    Usage:
        mgr.subscribe(task_id)   → get a queue to read from
        mgr.push(task_id, line)  → push a log line (non-blocking)
        mgr.done(task_id)        → signal stream end (sentinel None)
        mgr.unsubscribe(task_id) → cleanup
    """

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[Any]] = {}

    def subscribe(self, task_id: str) -> asyncio.Queue[Any]:
        q: asyncio.Queue[Any] = asyncio.Queue()
        self._queues[task_id] = q
        return q

    def unsubscribe(self, task_id: str) -> None:
        self._queues.pop(task_id, None)

    def push(self, task_id: str, line: str) -> None:
        q = self._queues.get(task_id)
        if q is not None:
            try:
                q.put_nowait(line)
            except asyncio.QueueFull:
                pass

    def done(self, task_id: str) -> None:
        q = self._queues.get(task_id)
        if q is not None:
            try:
                q.put_nowait(None)  # sentinel: stream complete
            except asyncio.QueueFull:
                pass
