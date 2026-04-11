"""SSE subscription manager: per-task event buffering and streaming."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any, Union

from manim_agent.pipeline_events import EventType, PipelineEvent
from backend.models import SSEEvent

_MAX_BUFFER_SIZE = 500


def sse_event_name(event_type: EventType) -> str:
    return event_type.value


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SSESubscriptionManager:
    """Manages per-task event buffering and asyncio.Queue subscriptions."""

    def __init__(self) -> None:
        self._buffers: dict[str, deque[str]] = {}
        self._subscribers: dict[str, list[asyncio.Queue[Any]]] = {}
        self._logger = logging.getLogger(__name__)

    def subscribe(self, task_id: str, *, replay: bool = True) -> asyncio.Queue[Any]:
        """Create a subscription queue and replay cached events when requested."""
        q: asyncio.Queue[Any] = asyncio.Queue()
        self._logger.debug(
            "SSE subscribe task=%s replay=%s existing=%d",
            task_id,
            replay,
            len(self._subscribers.get(task_id, [])),
        )

        buf = self._buffers.get(task_id)
        if replay and buf:
            for item in buf:
                try:
                    q.put_nowait(item)
                except asyncio.QueueFull:
                    break

        subscribers = self._subscribers.setdefault(task_id, [])
        subscribers.append(q)
        self._logger.debug(
            "SSE subscribed task=%s replayed=%d total=%d",
            task_id,
            len(buf or []),
            len(subscribers),
        )
        return q

    def unsubscribe(self, task_id: str, queue: asyncio.Queue[Any]) -> None:
        subs = self._subscribers.get(task_id)
        if subs:
            try:
                subs.remove(queue)
            except ValueError:
                pass
            if not subs:
                self._subscribers.pop(task_id, None)
        self._logger.debug(
            "SSE unsubscribe task=%s remaining=%d",
            task_id,
            len(self._subscribers.get(task_id, [])),
        )

    def cleanup(self, task_id: str) -> None:
        self._buffers.pop(task_id, None)
        self._subscribers.pop(task_id, None)
        self._logger.debug("SSE cleanup task=%s", task_id)

    def push(self, task_id: str, data: Union[str, PipelineEvent]) -> None:
        """Serialize and send event to all active subscribers."""
        serialized = self._serialize(data)
        if serialized is None:
            self._logger.debug("SSE push skipped task=%s", task_id)
            return

        buf = self._buffers.setdefault(task_id, deque(maxlen=_MAX_BUFFER_SIZE))
        buf.append(serialized)
        self._logger.debug(
            "SSE push task=%s size=%d buffer=%d",
            task_id,
            len(buf),
            len(serialized),
        )

        for q in self._subscribers.get(task_id, []):
            try:
                q.put_nowait(serialized)
            except asyncio.QueueFull:
                self._logger.warning("SSE subscriber queue full task=%s", task_id)

    def done(self, task_id: str) -> None:
        self._logger.debug(
            "SSE done task=%s subscribers=%d",
            task_id,
            len(self._subscribers.get(task_id, [])),
        )
        for q in self._subscribers.get(task_id, []):
            try:
                q.put_nowait(None)
            except asyncio.QueueFull:
                self._logger.warning("SSE done queue full task=%s", task_id)

        self._subscribers.pop(task_id, None)
        self._logger.debug("SSE done complete task=%s", task_id)

    def get_buffer(self, task_id: str) -> list[str]:
        buf = self._buffers.get(task_id)
        return list(buf) if buf else []

    @staticmethod
    def _serialize(data: Union[str, PipelineEvent]) -> str | None:
        if isinstance(data, PipelineEvent):
            payload_data: Any = data.data
            if not isinstance(payload_data, str):
                payload_data = payload_data.model_dump()

            sse = SSEEvent(
                event_type=sse_event_name(data.event_type),
                data=payload_data,
                timestamp=data.timestamp,
            )
            return sse.model_dump_json(by_alias=True)

        if not isinstance(data, str):
            return None
        sse = SSEEvent(
            event_type="log",
            data=data,
            timestamp=_now_iso(),
        )
        return sse.model_dump_json(by_alias=True)

