"""Tests for Phase 边界成对事件 PHASE_ENTER / PHASE_EXIT（P1）。

覆盖：PhaseBoundaryPayload 模型业务字段、成对发射、
元数据携带、与 TraceSpan 的关联。
"""

from __future__ import annotations

import pytest

from manim_agent.pipeline_events import (
    EventType,
    PhaseBoundaryPayload,
    PipelineEvent,
)


class TestPhaseBoundaryPayload:
    def test_enter_payload_carries_phase_metadata(self):
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

    def test_exit_payload_carries_execution_metadata(self):
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
        assert events[0].data.duration_ms is not None
        assert events[0].data.duration_ms >= 0

    def test_null_callback_is_noop(self):
        from manim_agent.pipeline_config import emit_phase_enter, emit_phase_exit
        emit_phase_enter(None, phase_id="p1", phase_name="test")
        emit_phase_exit(None, phase_id="p1", phase_name="test")

    def test_exit_without_prior_enter_still_works(self):
        """没有对应 enter 的 exit 不应崩溃。"""
        from manim_agent.pipeline_config import emit_phase_exit

        events: list = []
        emit_phase_exit(events.append, phase_id="orphan", phase_name="Orphan")
        assert len(events) == 1
        assert events[0].data.action == "exit"
