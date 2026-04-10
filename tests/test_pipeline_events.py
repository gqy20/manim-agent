"""Tests for manim_agent.pipeline_events module (结构化事件类型系统).

覆盖：事件类型枚举、PipelineEvent 模型校验、序列化、
工具调用生命周期、思考块、进度追踪。
"""

from __future__ import annotations

import time
import pytest

# 导入目标模块（实现前 ImportError —— 红灯）
from manim_agent.pipeline_events import (
    EventType,
    PipelineEvent,
    ToolStartPayload,
    ToolResultPayload,
    ThinkingPayload,
    ProgressPayload,
)


# ── EventType 枚举 ───────────────────────────────────────────────


class TestEventType:
    def test_has_log_type(self):
        assert "log" in [e.value for e in EventType]

    def test_has_status_type(self):
        assert "status" in [e.value for e in EventType]

    def test_has_error_type(self):
        assert "error" in [e.value for e in EventType]

    def test_has_tool_start_type(self):
        assert "tool_start" in [e.value for e in EventType]

    def test_has_tool_result_type(self):
        assert "tool_result" in [e.value for e in EventType]

    def test_has_thinking_type(self):
        assert "thinking" in [e.value for e in EventType]

    def test_has_progress_type(self):
        assert "progress" in [e.value for e in EventType]

    def test_total_event_types(self):
        """应包含所有调试所需的事件类别。"""
        expected = {
            "log", "status", "error",
            "tool_start", "tool_result",
            "thinking", "progress",
        }
        actual = {e.value for e in EventType}
        assert expected == actual


# ── PipelineEvent 模型 ───────────────────────────────────────────


class TestPipelineEventLog:
    """纯文本日志事件（向后兼容）。"""

    def test_log_event_creation(self):
        evt = PipelineEvent(
            event_type=EventType.LOG,
            data="hello world",
        )
        assert evt.event_type == EventType.LOG
        assert evt.data == "hello world"
        assert evt.timestamp is not None

    def test_log_event_serializable(self):
        evt = PipelineEvent(event_type=EventType.LOG, data="test")
        d = evt.model_dump()
        assert d["event_type"] == "log"
        assert d["data"] == "test"
        assert "timestamp" in d


class TestPipelineEventStatus:
    """状态变更事件。"""

    def test_status_pending(self):
        evt = PipelineEvent(
            event_type=EventType.STATUS,
            data="pending",
        )
        assert evt.data == "pending"

    def test_all_statuses_valid(self):
        for status in ("pending", "running", "completed", "failed"):
            evt = PipelineEvent(event_type=EventType.STATUS, data=status)
            assert evt.event_type == EventType.STATUS
            assert evt.data == status


class TestPipelineEventError:
    """错误事件。"""

    def test_error_with_message(self):
        evt = PipelineEvent(
            event_type=EventType.ERROR,
            data="Something went wrong",
        )
        assert evt.event_type == EventType.ERROR
        assert "wrong" in evt.data


class TestPipelineEventToolStart:
    """工具调用开始事件。"""

    def test_minimal(self):
        payload = ToolStartPayload(
            tool_use_id="tu_001",
            name="Write",
            input_summary={"file_path": "scene.py"},
        )
        evt = PipelineEvent(
            event_type=EventType.TOOL_START,
            data=payload,
        )
        assert evt.event_type == EventType.TOOL_START
        assert evt.data.name == "Write"

    def test_full_payload(self):
        payload = ToolStartPayload(
            tool_use_id="tu_001",
            name="Bash",
            input_summary={"command": "manim -qh scene.py Scene"},
        )
        evt = PipelineEvent(event_type=EventType.TOOL_START, data=payload)
        d = evt.model_dump()
        assert d["data"]["tool_use_id"] == "tu_001"
        assert d["data"]["name"] == "Bash"

    def test_invalid_missing_required_fields(self):
        with pytest.raises(Exception):  # Validation error
            ToolStartPayload(name="Write")  # 缺少 tool_use_id


class TestPipelineEventToolResult:
    """工具调用结果事件。"""

    def test_success_result(self):
        payload = ToolResultPayload(
            tool_use_id="tu_001",
            name="Bash",
            is_error=False,
            content="Rendered in 8.5s",
            duration_ms=8500,
        )
        evt = PipelineEvent(
            event_type=EventType.TOOL_RESULT,
            data=payload,
        )
        assert evt.data.is_error is False
        assert evt.data.content == "Rendered in 8.5s"

    def test_error_result(self):
        payload = ToolResultPayload(
            tool_use_id="tu_001",
            name="Bash",
            is_error=True,
            content="Exit code 1",
            duration_ms=200,
        )
        evt = PipelineEvent(event_type=EventType.TOOL_RESULT, data=payload)
        assert evt.data.is_error is True

    def test_content_can_be_none_for_success(self):
        """成功时 content 可以为 None（如 Write 工具无输出）。"""
        payload = ToolResultPayload(
            tool_use_id="tu_001",
            name="Write",
            is_error=False,
            content=None,
            duration_ms=50,
        )
        evt = PipelineEvent(event_type=EventType.TOOL_RESULT, data=payload)
        assert evt.data.content is None


class TestPipelineEventThinking:
    """思考/推理事件。"""

    def test_basic(self):
        payload = ThinkingPayload(
            thinking="I need to create a Fourier transform...",
            preview="I need to create a Fourier...",
            signature="sig-abc",
        )
        evt = PipelineEvent(
            event_type=EventType.THINKING,
            data=payload,
        )
        assert "Fourier" in evt.data.thinking

    def test_preview_auto_truncated_when_long(self):
        """长 thinking 文本自动截断 preview。"""
        long_text = "x" * 200
        payload = ThinkingPayload(
            thinking=long_text,
            preview=None,  # 应自动截断
            signature="sig",
        )
        evt = PipelineEvent(event_type=EventType.THINKING, data=payload)
        assert len(evt.data.preview) <= 100


class TestPipelineEventProgress:
    """进度追踪事件。"""

    def test_basic(self):
        payload = ProgressPayload(
            turn=3,
            total_tokens=15000,
            tool_uses=7,
            elapsed_ms=12000,
            last_tool_name="Bash",
        )
        evt = PipelineEvent(
            event_type=EventType.PROGRESS,
            data=payload,
        )
        assert evt.data.turn == 3
        assert evt.data.total_tokens == 15000

    def test_elapsed_must_be_non_negative(self):
        with pytest.raises(Exception):  # validation
            ProgressPayload(
                turn=1, total_tokens=100,
                tool_uses=0, elapsed_ms=-1,
            )


# ── 序列化往返兼容性 ──────────────────────────────────────────


class TestRoundtripSerialization:
    """验证 PipelineEvent 可序列化→反序列化，且与 SSEEvent 兼容。"""

    def test_log_roundtrip(self):
        original = PipelineEvent(event_type=EventType.LOG, data="test line")
        serialized = original.model_dump()
        restored = PipelineEvent.model_validate(serialized)
        assert restored.event_type == EventType.LOG
        assert restored.data == "test line"

    def test_tool_start_roundtrip(self):
        payload = ToolStartPayload(
            tool_use_id="tu_001",
            name="Edit",
            input_summary={"file_path": "scene.py"},
        )
        original = PipelineEvent(event_type=EventType.TOOL_START, data=payload)
        restored = PipelineEvent.model_validate(original.model_dump())
        assert restored.data.tool_use_id == "tu_001"

    def test_tool_result_roundtrip(self):
        payload = ToolResultPayload(
            tool_use_id="tu_002",
            name="Read",
            is_error=False,
            content="file contents here",
            duration_ms=100,
        )
        original = PipelineEvent(
            event_type=EventType.TOOL_RESULT, data=payload,
        )
        restored = PipelineEvent.model_validate(original.model_dump())
        assert restored.data.content == "file contents here"

    def test_thinking_roundtrip(self):
        payload = ThinkingPayload(
            thinking="deep thoughts",
            preview="deep thoughts",
            signature="sig-xyz",
        )
        original = PipelineEvent(event_type=EventType.THINKING, data=payload)
        restored = PipelineEvent.model_validate(original.model_dump())
        assert restored.data.signature == "sig-xyz"

    def test_progress_roundtrip(self):
        payload = ProgressPayload(
            turn=5, total_tokens=9999, tool_uses=12,
            elapsed_ms=30000, last_tool_name="Write",
        )
        original = PipelineEvent(event_type=EventType.PROGRESS, data=payload)
        restored = PipelineEvent.model_validate(original.model_dump())
        assert restored.data.turn == 5

    def test_timestamp_auto_generated(self):
        """不传 timestamp 时自动生成。"""
        before = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())
        evt = PipelineEvent(event_type=EventType.LOG, data="t")
        after = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())
        # timestamp 是字符串，与同格式字符串比较
        assert before <= evt.timestamp <= after

    def test_timestamp_preserved(self):
        """显式传入 timestamp 时保留。"""
        ts = "2026-04-11T12:00:00+00:00"
        evt = PipelineEvent(event_type=EventType.LOG, data="t", timestamp=ts)
        assert evt.timestamp == ts
