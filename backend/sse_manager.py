"""SSE subscription manager: per-task event buffering & streaming.

支持两种数据格式：
- 纯文本字符串（向后兼容）
- PipelineEvent 结构化事件（自动序列化为 SSEEvent JSON）

v2 改进：
- 事件缓冲：push() 时即使无订阅者也会缓存事件（最多 500 条）
- 多订阅者：subscribe() 返回独立队列，不再覆盖旧队列
- 回放机制：新订阅者自动接收缓冲区中的历史事件
"""

from __future__ import annotations

import asyncio
from collections import deque
from typing import Any, Union

from manim_agent.pipeline_events import EventType, PipelineEvent
from backend.models import SSEEvent

# 每个任务最多缓冲的事件数量
_MAX_BUFFER_SIZE = 500


def sse_event_name(event_type: EventType) -> str:
    """将 PipelineEvent.EventType 映射为 SSE event field 值。"""
    return event_type.value


class SSESubscriptionManager:
    """Manages per-task event buffering and asyncio.Queue subscriptions.

    Usage:
        mgr.push(task_id, data)       # buffer + push to all subscribers
        q = mgr.subscribe(task_id)     # get queue (replays buffered events)
        mgr.done(task_id)              # signal stream end (sentinel None)
        mgr.unsubscribe(task_id, q)    # cleanup one subscriber
        mgr.cleanup(task_id)           # remove all state for task
    """

    def __init__(self) -> None:
        # task_id → deque of serialized event strings (循环缓冲)
        self._buffers: dict[str, deque[str]] = {}
        # task_id → list of active subscriber queues
        self._subscribers: dict[str, list[asyncio.Queue[Any]]] = {}

    def subscribe(self, task_id: str) -> asyncio.Queue[Any]:
        """创建新的订阅队列，并回放缓冲区中的历史事件。

        注意：每次调用返回**独立的**队列，不会覆盖已有订阅者。
        """
        q: asyncio.Queue[Any] = asyncio.Queue()

        # 回放缓冲事件到新队列
        buf = self._buffers.get(task_id)
        if buf:
            for item in buf:
                try:
                    q.put_nowait(item)
                except asyncio.QueueFull:
                    pass

        # 注册订阅者
        self._subscribers.setdefault(task_id, []).append(q)
        return q

    def unsubscribe(self, task_id: str, queue: asyncio.Queue[Any]) -> None:
        """移除单个订阅者（不影响其他订阅者）。"""
        subs = self._subscribers.get(task_id)
        if subs:
            try:
                subs.remove(queue)
            except ValueError:
                pass

    def cleanup(self, task_id: str) -> None:
        """清理任务的所有状态（缓冲区 + 订阅者）。"""
        self._buffers.pop(task_id, None)
        self._subscribers.pop(task_id, None)

    def push(self, task_id: str, data: Union[str, PipelineEvent]) -> None:
        """推送数据：写入缓冲区 + 广播给所有活跃订阅者。

        - str: 包装为 SSEEvent(type="log", data=...)
        - PipelineEvent: 根据 event_type 序列化为对应 SSEEvent
        """
        # 序列化
        serialized = self._serialize(data)
        if serialized is None:
            return

        # 写入缓冲区（即使没有订阅者也保存，支持延迟连接回放）
        buf = self._buffers.setdefault(task_id, deque(maxlen=_MAX_BUFFER_SIZE))
        buf.append(serialized)

        # 广播给所有活跃订阅者
        for q in self._subscribers.get(task_id, []):
            try:
                q.put_nowait(serialized)
            except asyncio.QueueFull:
                pass

    def done(self, task_id: str) -> None:
        """向所有订阅者发送结束哨兵。"""
        for q in self._subscribers.get(task_id, []):
            try:
                q.put_nowait(None)  # sentinel: stream complete
            except asyncio.QueueFull:
                pass

    def get_buffer(self, task_id: str) -> list[str]:
        """获取任务的缓冲事件列表（用于调试/测试）。"""
        buf = self._buffers.get(task_id)
        return list(buf) if buf else []

    # ── 内部序列化 ────────────────────────────────────────────

    @staticmethod
    def _serialize(data: Union[str, PipelineEvent]) -> str | None:
        """将原始数据序列化为 SSEEvent JSON 字符串。"""
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
        else:
            sse = SSEEvent(
                event_type="log",
                data=data,
                timestamp=_now_iso(),
            )
            return sse.model_dump_json(by_alias=True)


def _now_iso() -> str:
    """返回当前 UTC 时间 ISO 8601 字符串。"""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
