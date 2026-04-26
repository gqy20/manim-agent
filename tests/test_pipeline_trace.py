"""Tests for manim_agent.pipeline_trace module (Trace/Span 可观测性模型).

覆盖：TraceSpan 数据模型、上下文管理器、trace_id 传播、
span 嵌套、序列化、与 PipelineEvent 的集成。
"""

from __future__ import annotations

import time

import pytest

# 导入目标模块（实现前 ImportError —— 红灯）
from manim_agent.pipeline_trace import (
    SpanStatus,
    TraceSpan,
    create_trace_id,
    get_current_span,
    get_current_trace_id,
    in_trace_context,
    push_span,
    pop_span,
    span_context,
)


# ── GetCurrentTraceId ────────────────────────────────────────────


class TestGetCurrentTraceId:
    def test_none_outside_context(self):
        assert get_current_trace_id() is None

    def test_returns_trace_id_inside_context(self):
        tid = create_trace_id()
        with span_context(trace_id=tid, span_name="root"):
            assert get_current_trace_id() == tid


# ── SpanStatus 枚举 ────────────────────────────────────────────


class TestSpanStatus:
    def test_has_expected_values(self):
        expected = {"ok", "error", "cancelled"}
        actual = {s.value for s in SpanStatus}
        assert expected == actual


# ── TraceSpan 数据模型 ────────────────────────────────────────


class TestTraceSpanModel:
    def test_minimal_creation(self):
        span = TraceSpan(
            trace_id="t-1",
            span_id="s-1",
            name="phase1_planning",
        )
        assert span.trace_id == "t-1"
        assert span.span_id == "s-1"
        assert span.name == "phase1_planning"
        assert span.parent_span_id is None
        assert span.status == SpanStatus.OK
        assert span.start_ms > 0
        assert span.end_ms is None
        assert span.tags == {}

    def test_full_creation(self):
        now = int(time.time() * 1000)
        span = TraceSpan(
            trace_id="t-1",
            span_id="s-1",
            parent_span_id="s-0",
            name="phase2_implementation",
            phase="phase2",
            start_ms=now,
            end_ms=now + 50000,
            status=SpanStatus.OK,
            tags={"beats": 3, "quality": "high"},
        )
        assert span.parent_span_id == "s-0"
        assert span.phase == "phase2"
        assert span.end_ms == now + 50000
        assert span.tags["beats"] == 3

    def test_duration_ms_when_open(self):
        span = TraceSpan(trace_id="t-1", span_id="s-1", name="test")
        # end_ms 为 None 时 duration 返回 None
        assert span.duration_ms is None

    def test_duration_ms_when_closed(self):
        span = TraceSpan(
            trace_id="t-1", span_id="s-1", name="test",
            start_ms=1000, end_ms=5500,
        )
        assert span.duration_ms == 4500

    def test_serializable_to_dict(self):
        span = TraceSpan(
            trace_id="t-1", span_id="s-1", name="render",
            phase="phase3", tags={"segments": 5},
        )
        d = span.to_dict()
        assert d["trace_id"] == "t-1"
        assert d["name"] == "render"
        assert d["phase"] == "phase3"
        assert d["tags"]["segments"] == 5
        assert "duration_ms" in d

    def test_close_sets_end_ms_and_status(self):
        span = TraceSpan(trace_id="t-1", span_id="s-1", name="test")
        assert span.end_ms is None
        before = int(time.time() * 1000)
        span.close()
        after = int(time.time() * 1000)
        assert span.end_ms is not None
        assert before <= span.end_ms <= after
        assert span.status == SpanStatus.OK

    def test_close_with_error_status(self):
        span = TraceSpan(trace_id="t-1", span_id="s-1", name="test")
        span.close(status=SpanStatus.ERROR)
        assert span.status == SpanStatus.ERROR

    def test_roundtrip_dict_to_model(self):
        original = TraceSpan(
            trace_id="t-1", span_id="s-1", parent_span_id="s-0",
            name="mux", phase="phase5",
            start_ms=1000, end_ms=3000,
            status=SpanStatus.OK, tags={"bgm": True},
        )
        restored = TraceSpan.from_dict(original.to_dict())
        assert restored.trace_id == original.trace_id
        assert restored.name == original.name
        assert restored.tags == original.tags
        assert restored.duration_ms == original.duration_ms


# ── 上下文管理器 span_context ────────────────────────────────


class TestSpanContextManager:
    def test_root_span_creates_new_span(self):
        tid = create_trace_id()
        with span_context(trace_id=tid, span_name="pipeline") as span:
            assert span.trace_id == tid
            assert span.name == "pipeline"
            assert span.parent_span_id is None
            assert span.end_ms is None  # 还在运行中

    def test_nested_spans_set_parent(self):
        tid = create_trace_id()
        with span_context(trace_id=tid, span_name="root") as root:
            with span_context(span_name="child") as child:
                assert child.parent_span_id == root.span_id
                assert child.trace_id == tid

    def test_three_level_nesting(self):
        tid = create_trace_id()
        with span_context(trace_id=tid, span_name="p1") as s1:
            with span_context(span_name="p2") as s2:
                with span_context(span_name="p3") as s3:
                    assert s3.parent_span_id == s2.span_id
                    assert s2.parent_span_id == s1.span_id
                    assert s1.parent_span_id is None

    def test_exit_closes_span(self):
        tid = create_trace_id()
        with span_context(trace_id=tid, span_name="test") as span:
            assert span.end_ms is None
        # exit 后应自动 close
        assert span.end_ms is not None

    def test_exception_sets_error_status(self):
        tid = create_trace_id()
        with pytest.raises(RuntimeError):
            with span_context(trace_id=tid, span_name="fail") as span:
                raise RuntimeError("boom")
        assert span.status == SpanStatus.ERROR

    def test_get_current_span_returns_active(self):
        tid = create_trace_id()
        assert get_current_span() is None
        with span_context(trace_id=tid, span_name="active") as span:
            assert get_current_span() is span
        assert get_current_span() is None

    def test_in_trace_context_guard(self):
        assert in_trace_context() is False
        with span_context(trace_id=create_trace_id(), span_name="x"):
            assert in_trace_context() is True
        assert in_trace_context() is False

    def test_tags_merged_into_span(self):
        tid = create_trace_id()
        with span_context(
            trace_id=tid, span_name="tagged",
            phase="phase2", beats=3, quality="high",
        ) as span:
            assert span.phase == "phase2"
            assert span.tags["beats"] == 3
            assert span.tags["quality"] == "high"

    def test_phase_propagates_from_kwarg_or_tags(self):
        """phase 可以通过显式参数或 tags 字典传入。"""
        tid = create_trace_id()
        # 显式 phase 参数
        with span_context(trace_id=tid, span_name="a", phase="p1") as sa:
            assert sa.phase == "p1"
        # tags 中的 phase 应被提取为显式字段
        with span_context(trace_id=tid, span_name="b", _phase="p2") as sb:
            assert sb.phase == "p2"


# ── push/pop 手动管理（给 dispatcher 等非 context 场景用） ──


class TestPushPopSpan:
    def test_push_and_retrieve(self):
        tid = create_trace_id()
        span = TraceSpan(trace_id=tid, span_id="s-1", name="manual")
        push_span(span)
        try:
            assert get_current_span() is span
            assert get_current_trace_id() == tid
        finally:
            pop_span()
        assert get_current_span() is None

    def test_push_multiple_pops_lifo(self):
        tid = create_trace_id()
        s1 = TraceSpan(trace_id=tid, span_id="s-1", name="outer")
        s2 = TraceSpan(trace_id=tid, span_id="s-2", name="inner")
        push_span(s1)
        push_span(s2)
        assert get_current_span() is s2
        pop_span()
        assert get_current_span() is s1
        pop_span()

    def test_pop_empty_is_noop(self):
        pop_span()  # 不应抛异常


# ── 与 PipelineEvent 集成 ─────────────────────────────────────


class TestTraceSpanPipelineEventIntegration:
    def test_span_emits_enter_and_exit_events(self):
        """span_context 在进入/退出时发射 TRACE_SPAN 事件。"""
        from manim_agent.pipeline_events import EventType, PipelineEvent

        events: list = []
        tid = create_trace_id()

        original_emit = getattr(TraceSpan, "_emit_event_fn", None)

        def capture_event(evt):
            events.append(evt)

        TraceSpan._emit_event_fn = capture_event
        try:
            with span_context(trace_id=tid, span_name="test_phase", phase="phase1"):
                pass
        finally:
            TraceSpan._emit_event_fn = original_emit

        # 应有 ENTER + EXIT 两个事件
        trace_events = [e for e in events if e.event_type == EventType.TRACE_SPAN]
        assert len(trace_events) >= 2
        assert trace_events[0].data.action == "enter"
        assert trace_events[-1].data.action == "exit"

    def test_span_event_carries_trace_metadata(self):
        from manim_agent.pipeline_events import EventType, TraceSpanPayload

        events: list = []
        tid = create_trace_id()

        TraceSpan._emit_event_fn = events.append
        try:
            with span_context(trace_id=tid, span_name="p2", phase="phase2", turns=5):
                pass
        finally:
            TraceSpan._emit_event_fn = None

        enter = [e for e in events if e.event_type == EventType.TRACE_SPAN and e.data.action == "enter"][0]
        assert isinstance(enter.data, TraceSpanPayload)
        assert enter.data.trace_id == tid
        assert enter.data.span_name == "p2"
        assert enter.data.phase == "phase2"


