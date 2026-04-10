"""Tests for structured SSE event integration (Phase A2).

覆盖：SSEEvent 结构化数据支持、SSEManager 推送 PipelineEvent、
路由层事件类型分发。
"""

from __future__ import annotations

import json
import pytest

from manim_agent.pipeline_events import (
    EventType,
    PipelineEvent,
    ToolStartPayload,
    ToolResultPayload,
    ThinkingPayload,
    ProgressPayload,
)
from backend.models import SSEEvent
from backend.sse_manager import SSESubscriptionManager, sse_event_name


# ── SSEEvent 结构化数据支持 ────────────────────────────────


class TestSSEEventStructuredData:
    """SSEEvent 应能承载结构化数据（不仅仅是纯文本）。"""

    def test_data_can_be_string(self):
        """向后兼容：data 仍可为字符串。"""
        evt = SSEEvent(
            event_type="log", data="hello",
            timestamp="2026-01-01T00:00:00Z",
        )
        assert evt.data == "hello"

    def test_data_can_be_dict(self):
        """新增：data 可为字典（结构化载荷）。"""
        payload = {"tool_use_id": "tu_1", "name": "Bash"}
        evt = SSEEvent(
            event_type="tool_start", data=payload,
            timestamp="2026-01-01T00:00:00Z",
        )
        assert evt.data == payload

    def test_serialization_with_dict_data(self):
        """含 dict data 的 SSEEvent 可正确序列化为 JSON。"""
        evt = SSEEvent(
            event_type="tool_start",
            data={"name": "Write", "file_path": "scene.py"},
            timestamp="2026-01-01T00:00:00Z",
        )
        raw = evt.model_dump_json()
        parsed = json.loads(raw)
        assert parsed["data"]["name"] == "Write"

    def test_from_pipeline_event_log(self):
        """从 PipelineEvent(LOG) 构建 SSEEvent 保持字符串 data。"""
        pe = PipelineEvent(event_type=EventType.LOG, data="render started")
        sse = SSEEvent(
            event_type=pe.event_type.value,
            data=pe.data,
            timestamp=pe.timestamp,
        )
        assert sse.event_type == "log"
        assert sse.data == "render started"

    def test_from_pipeline_event_tool_start(self):
        """从 PipelineEvent(TOOL_START) 构建 SSEEvent 携带结构化 data。"""
        payload = ToolStartPayload(
            tool_use_id="tu_001",
            name="Bash",
            input_summary={"command": "manim scene.py"},
        )
        pe = PipelineEvent(event_type=EventType.TOOL_START, data=payload)
        sse = SSEEvent(
            event_type=pe.event_type.value,
            data=pe.data.model_dump(),
            timestamp=pe.timestamp,
        )
        assert sse.event_type == "tool_start"
        assert sse.data["name"] == "Bash"

    def test_from_pipeline_event_thinking(self):
        """从 PipelineEvent(THINKING) 构建 SSEEvent。"""
        payload = ThinkingPayload(
            thinking="Let me think...",
            preview="Let me think...",
            signature="sig-1",
        )
        pe = PipelineEvent(event_type=EventType.THINKING, data=payload)
        sse = SSEEvent(
            event_type=pe.event_type.value,
            data=pe.data.model_dump(),
            timestamp=pe.timestamp,
        )
        assert sse.event_type == "thinking"
        assert "think" in sse.data["preview"]

    def test_from_pipeline_event_progress(self):
        """从 PipelineEvent(PROGRESS) 构建 SSEEvent。"""
        payload = ProgressPayload(
            turn=3, total_tokens=5000,
            tool_uses=5, elapsed_ms=10000,
        )
        pe = PipelineEvent(event_type=EventType.PROGRESS, data=payload)
        sse = SSEEvent(
            event_type=pe.event_type.value,
            data=pe.data.model_dump(),
            timestamp=pe.timestamp,
        )
        assert sse.event_type == "progress"
        assert sse.data["turn"] == 3


# ── SSESubscriptionManager 推送 PipelineEvent ───────────────


class TestSSEManagerStructuredPush:
    """SSEManager 应能推送 PipelineEvent 对象（自动序列化）。"""

    def test_push_string_still_works(self):
        """向后兼容：push 字符串包装为 log 类型 SSEEvent。"""
        mgr = SSESubscriptionManager()
        q = mgr.subscribe("t1")
        mgr.push("t1", "plain text")
        item = q.get_nowait()
        parsed = json.loads(item)
        assert parsed["type"] == "log"
        assert parsed["data"] == "plain text"

    def test_push_pipeline_event(self):
        """推送 PipelineEvent 时，队列中应得到序列化后的 SSEEvent 字符串。"""
        mgr = SSESubscriptionManager()
        q = mgr.subscribe("t2")
        pe = PipelineEvent(
            event_type=EventType.TOOL_START,
            data=ToolStartPayload(
                tool_use_id="tu_1", name="Write",
                input_summary={"file": "scene.py"},
            ),
        )
        mgr.push("t2", pe)
        item = q.get_nowait()
        # 应为 JSON 字符串（SSEEvent 序列化结果）
        parsed = json.loads(item)
        assert parsed["type"] == "tool_start"
        assert parsed["data"]["name"] == "Write"

    def test_push_log_pipeline_event(self):
        """LOG 类型 PipelineEvent 推送后保持字符串格式。"""
        mgr = SSESubscriptionManager()
        q = mgr.subscribe("t3")
        pe = PipelineEvent(event_type=EventType.LOG, data="simple log line")
        mgr.push("t3", pe)
        item = q.get_nowait()
        parsed = json.loads(item)
        assert parsed["type"] == "log"
        assert parsed["data"] == "simple log line"

    def test_push_to_nonexistent_task_no_crash(self):
        """向不存在的 task_id 推送不应崩溃。"""
        mgr = SSESubscriptionManager()
        pe = PipelineEvent(event_type=EventType.LOG, data="test")
        # 不应抛异常
        mgr.push("nonexistent", pe)

    def test_mixed_string_and_pipeline_events(self):
        """同一任务可混合接收字符串和 PipelineEvent。"""
        mgr = SSESubscriptionManager()
        q = mgr.subscribe("t4")
        mgr.push("t4", "text line")
        mgr.push("t4", PipelineEvent(
            event_type=EventType.TOOL_RESULT,
            data=ToolResultPayload(
                tool_use_id="tu_1", name="Bash",
                is_error=False, content="ok", duration_ms=100,
            ),
        ))
        mgr.push("t4", "another text")

        # 第一个：纯文本
        item1 = q.get_nowait()
        p1 = json.loads(item1)
        assert p1["type"] == "log"
        assert p1["data"] == "text line"

        # 第二个：结构化事件
        item2 = q.get_nowait()
        p2 = json.loads(item2)
        assert p2["type"] == "tool_result"
        assert p2["data"]["name"] == "Bash"

        # 第三个：纯文本
        item3 = q.get_nowait()
        p3 = json.loads(item3)
        assert p3["type"] == "log"
        assert p3["data"] == "another text"


# ── 事件类型映射辅助函数 ────────────────────────────────────


class TestEventMapping:
    """验证 EventType → SSE event name 的映射逻辑。"""

    def test_log_maps_to_log_sse_event(self):
        assert _sse_event_name(EventType.LOG) == "log"

    def test_status_maps_to_status_sse_event(self):
        assert _sse_event_name(EventType.STATUS) == "status"

    def test_error_maps_to_error_sse_event(self):
        assert _sse_event_name(EventType.ERROR) == "error"

    def test_tool_start_maps_to_tool_start(self):
        assert _sse_event_name(EventType.TOOL_START) == "tool_start"

    def test_tool_result_maps_to_tool_result(self):
        assert _sse_event_name(EventType.TOOL_RESULT) == "tool_result"

    def test_thinking_maps_to_thinking(self):
        assert _sse_event_name(EventType.THINKING) == "thinking"

    def test_progress_maps_to_progress(self):
        assert _sse_event_name(EventType.PROGRESS) == "progress"


# 直接使用 sse_event_name（从 backend.sse_manager 导入）
_sse_event_name = sse_event_name
