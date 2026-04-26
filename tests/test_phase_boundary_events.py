"""Tests for Phase 边界成对事件 PHASE_ENTER / PHASE_EXIT（P1）。

覆盖：PhaseBoundaryPayload 模型、成对发射、
元数据携带、序列化、与 TraceSpan 的关联。
"""

from __future__ import annotations

import time

import pytest

from manim_agent.pipeline_events import (
    EventType,
    PhaseBoundaryPayload,
    PipelineEvent,
)


# ── PhaseBoundaryPayload 模型 ─────────────────────────────────


class TestPhaseBoundaryPayload:
    def test_enter_payload(self):
        p = PhaseBoundaryPayload(
            action="enter",
            phase_name="phase1_planning",
            phase_id="phase1",
            trace_id="t-123",
        )
        assert p.action == "enter"
        assert p.phase_name == "phase1_planning"
        assert p.phase_id == "phase1"
        assert p.trace_id == "t-123"

    def test_exit_payload_with_metadata(self):
        p = PhaseBoundaryPayload(
            action="exit",
            phase_name="phase2_implementation",
            phase_id="phase2",
            duration_ms=32000,
            status="ok",
            beats_count=5,
            turn_count=42,
            trace_id="t-456",
            metadata={"video_output": "/out/vid.mp4", "render_mode": "full"},
        )
        assert p.duration_ms == 32000
        assert p.beats_count == 5
        assert p.turn_count == 42
        assert p.metadata["video_output"] == "/out/vid.mp4"

    def test_action_must_be_valid(self):
        for action in ("enter", "exit"):
            p = PhaseBoundaryPayload(
                action=action, phase_name="x", phase_id="p1",
            )
            assert p.action == action

    def test_serializable(self):
        p = PhaseBoundaryPayload(
            action="enter", phase_name="narration", phase_id="phase3_5",
            trace_id="t-1",
        )
        d = p.model_dump()
        assert d["action"] == "enter"
        assert d["phase_name"] == "narration"
        restored = PhaseBoundaryPayload.model_validate(d)
        assert restored.action == "enter"


class TestPhaseBoundaryEvent:
    def test_enter_event_creation(self):
        evt = PipelineEvent(
            event_type=EventType.PHASE_BOUNDARY,
            data=PhaseBoundaryPayload(
                action="enter", phase_name="planning", phase_id="phase1",
                trace_id="t-1",
            ),
        )
        assert evt.event_type == EventType.PHASE_BOUNDARY
        assert evt.data.action == "enter"

    def test_roundtrip(self):
        original = PipelineEvent(
            event_type=EventType.PHASE_BOUNDARY,
            data=PhaseBoundaryPayload(
                action="exit", phase_name="mux", phase_id="phase5",
                duration_ms=5000, status="ok", trace_id="t-1",
            ),
        )
        restored = PipelineEvent.model_validate(original.model_dump())
        assert restored.event_type == EventType.PHASE_BOUNDARY
        assert restored.data.duration_ms == 5000


# ── emit_phase_enter / emit_phase_exit 便捷函数 ────────────────


class TestEmitPhaseBoundary:
    def test_emit_phase_enter_creates_event(self):
        from manim_agent.pipeline_config import emit_phase_enter

        events: list = []
        cb = events.append
        emit_phase_enter(cb, phase_id="phase1", phase_name="Scene Planning", trace_id="t-1")

        assert len(events) == 1
        assert events[0].event_type == EventType.PHASE_BOUNDARY
        assert events[0].data.action == "enter"
        assert events[0].data.phase_id == "phase1"
        assert events[0].data.phase_name == "Scene Planning"

    def test_emit_phase_exit_creates_event_with_duration(self):
        from manim_agent.pipeline_config import emit_phase_exit

        events: list = []
        cb = events.append
        emit_phase_exit(
            cb, phase_id="phase2", phase_name="Implementation",
            status="ok", turn_count=30, beats_count=8,
            trace_id="t-1",
        )

        assert len(events) == 1
        assert events[0].event_type == EventType.PHASE_BOUNDARY
        assert events[0].data.action == "exit"
        assert events[0].data.turn_count == 30
        assert events[0].data.beats_count == 8
        assert events[0].data.status == "ok"
        # duration_ms 应自动计算（从 enter 到 exit 的时间差）
        assert events[0].data.duration_ms is not None
        assert events[0].data.duration_ms >= 0

    def test_null_callback_is_noop(self):
        from manim_agent.pipeline_config import emit_phase_enter, emit_phase_exit
        # 不应抛异常
        emit_phase_enter(None, phase_id="p1", phase_name="test")
        emit_phase_exit(None, phase_id="p1", phase_name="test")

    def test_exit_without_prior_enter_still_works(self):
        """没有对应 enter 的 exit 不应崩溃。"""
        from manim_agent.pipeline_config import emit_phase_exit

        events: list = []
        emit_phase_exit(events.append, phase_id="orphan", phase_name="Orphan")
        assert len(events) == 1
        assert events[0].data.action == "exit"


# ── EventType 枚举扩展验证 ───────────────────────────────────


class TestEventTypeExtended:
    def test_includes_trace_span(self):
        values = {e.value for e in EventType}
        assert "trace_span" in values

    def test_includes_phase_boundary(self):
        values = {e.value for e in EventType}
        assert "phase_boundary" in values

    def test_total_event_types(self):
        """确认所有新增类型都在枚举中。"""
        expected = {
            "log", "status", "error",
            "tool_start", "tool_result",
            "thinking", "progress",
            "trace_span",       # 新增
            "phase_boundary",   # 新增
        }
        actual = {e.value for e in EventType}
        assert expected.issubset(actual)
