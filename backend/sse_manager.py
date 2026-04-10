"""SSE subscription manager: per-task asyncio.Queue for real-time log streaming.

支持两种数据格式：
- 纯文本字符串（向后兼容）
- PipelineEvent 结构化事件（自动序列化为 SSEEvent JSON）
"""

from __future__ import annotations

import asyncio
from typing import Any, Union

from manim_agent.pipeline_events import EventType, PipelineEvent
from backend.models import SSEEvent


def sse_event_name(event_type: EventType) -> str:
    """将 PipelineEvent.EventType 映射为 SSE event field 值。

    所有类型直接使用枚举值作为 SSE event name，
    前端据此分发到不同渲染器。
    """
    return event_type.value


class SSESubscriptionManager:
    """Manages per-task asyncio.Queue subscriptions for SSE streaming.

    Usage:
        mgr.subscribe(task_id)   → get a queue to read from
        mgr.push(task_id, data)  → push str or PipelineEvent (non-blocking)
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

    def push(self, task_id: str, data: Union[str, PipelineEvent]) -> None:
        """推送数据到任务队列。

        - str: 包装为 SSEEvent(type="log", data=...)
        - PipelineEvent: 根据 event_type 序列化为对应 SSEEvent
        """
        q = self._queues.get(task_id)
        if q is None:
            return

        if isinstance(data, PipelineEvent):
            payload_data: Any = data.data
            # 结构化载荷序列化为 dict，纯文本保持原样
            if not isinstance(payload_data, str):
                payload_data = payload_data.model_dump()

            sse = SSEEvent(
                event_type=sse_event_name(data.event_type),
                data=payload_data,
                timestamp=data.timestamp,
            )
            serialized = sse.model_dump_json(by_alias=True)
        else:
            # 向后兼容：纯文本包装为 log 类型
            sse = SSEEvent(
                event_type="log",
                data=data,
                timestamp=_now_iso(),
            )
            serialized = sse.model_dump_json(by_alias=True)

        try:
            q.put_nowait(serialized)
        except asyncio.QueueFull:
            pass

    def done(self, task_id: str) -> None:
        q = self._queues.get(task_id)
        if q is not None:
            try:
                q.put_nowait(None)  # sentinel: stream complete
            except asyncio.QueueFull:
                pass


def _now_iso() -> str:
    """返回当前 UTC 时间 ISO 8601 字符串。"""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
