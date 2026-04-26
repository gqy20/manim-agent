"""Trace/Span 可观测性模型：全链路追踪的上下文管理器与数据结构。

提供：
- TraceSpan：不可变 span 数据模型（trace_id, span_id, parent, phase, tags, timing）
- SpanStatus：ok / error / cancelled
- span_context()：上下文管理器，自动管理进入/退出 + 事件发射
- push_span() / pop_span()：手动栈管理（给 dispatcher 等非 context 场景）
- create_trace_id()：生成 UUID4 trace 标识符

设计原则：
- 基于 ContextVar 实现协程安全，不依赖全局可变状态
- 每个 span 在 enter/exit 时自动发射 TRACE_SPAN PipelineEvent
- 与 PipelineEvent 体系无缝集成，SSE 推送到前端 LogViewer
"""

from __future__ import annotations

import contextlib
import contextvars
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Generator, Optional

from .pipeline_events import EventType, PipelineEvent, TraceSpanPayload


# ── Span 状态 ────────────────────────────────────────────────────


class SpanStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    CANCELLED = "cancelled"


# ── TraceSpan 数据模型 ─────────────────────────────────────────


@dataclass
class TraceSpan:
    """一个不可变的执行区间（span），携带 trace 关联和元数据。

    典型生命周期：
        span = TraceSpan(trace_id=..., span_id=..., name="phase1_planning")
        # ... 执行中 ...
        span.close()   # 或 with span_context(): 自动 close
    """

    trace_id: str
    span_id: str = ""
    parent_span_id: Optional[str] = None
    name: str = ""
    phase: Optional[str] = None
    start_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    end_ms: Optional[int] = None
    status: SpanStatus = SpanStatus.OK
    tags: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.span_id:
            object.__setattr__(self, span_id := "span_id", f"span-{uuid.uuid4().hex[:12]}")

    @property
    def duration_ms(self) -> Optional[int]:
        if self.end_ms is None:
            return None
        return self.end_ms - self.start_ms

    def close(self, status: Optional[SpanStatus] = None) -> None:
        """标记 span 结束。"""
        if status is not None:
            object.__setattr__(self, "status", status)
        if self.end_ms is None:
            object.__setattr__(self, "end_ms", int(time.time() * 1000))

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "phase": self.phase,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "duration_ms": self.duration_ms,
            "status": self.status.value,
            "tags": dict(self.tags),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TraceSpan:
        status = d.get("status")
        return cls(
            trace_id=d["trace_id"],
            span_id=d["span_id"],
            parent_span_id=d.get("parent_span_id"),
            name=d["name"],
            phase=d.get("phase"),
            start_ms=d["start_ms"],
            end_ms=d.get("end_ms"),
            status=SpanStatus(status) if status else SpanStatus.OK,
            tags=dict(d.get("tags", {})),
        )

    # 可注入的事件发射回调（默认 noop，pipeline.py 启动时设置）
    _emit_event_fn: Optional[Callable[[PipelineEvent], None]] = None


# ── ContextVar 栈 ────────────────────────────────────────────────


_span_stack: contextvars.ContextVar[list[TraceSpan]] = contextvars.ContextVar(
    "manim_agent_span_stack", default=[]
)


def get_current_span() -> Optional[TraceSpan]:
    """返回当前活跃的 span（栈顶），无上下文时返回 None。"""
    stack = _span_stack.get()
    return stack[-1] if stack else None


def get_current_trace_id() -> Optional[str]:
    """返回当前 trace_id，无上下文时返回 None。"""
    span = get_current_span()
    return span.trace_id if span else None


def in_trace_context() -> bool:
    """是否在某个 trace/span 上下文中。"""
    return len(_span_stack.get()) > 0


def push_span(span: TraceSpan) -> None:
    """手动将 span 压入栈（给 dispatcher 等非 with 场景用）。"""
    stack = list(_span_stack.get())
    stack.append(span)
    _span_stack.set(stack)
    _emit_span_enter(span)


def pop_span() -> Optional[TraceSpan]:
    """弹出栈顶 span 并发射 exit 事件。空栈时不操作。"""
    stack = list(_span_stack.get())
    if not stack:
        return None
    span = stack.pop()
    _span_stack.set(stack)
    _emit_span_exit(span)
    return span


# ── 事件发射辅助 ────────────────────────────────────────────────


def _emit_span_enter(span: TraceSpan) -> None:
    _emit(TraceSpanPayload(
        action="enter",
        trace_id=span.trace_id,
        span_id=span.span_id,
        parent_span_id=span.parent_span_id,
        span_name=span.name,
        phase=span.phase,
    ))


def _emit_span_exit(span: TraceSpan) -> None:
    _emit(TraceSpanPayload(
        action="exit",
        trace_id=span.trace_id,
        span_id=span.span_id,
        parent_span_id=span.parent_span_id,
        span_name=span.name,
        phase=span.phase,
        status=span.status.value,
        duration_ms=span.duration_ms,
    ))


def _emit(payload: TraceSpanPayload) -> None:
    fn = TraceSpan._emit_event_fn
    if fn is not None:
        fn(PipelineEvent(event_type=EventType.TRACE_SPAN, data=payload))


# ── 上下文管理器 ────────────────────────────────────────────────


@contextlib.contextmanager
def span_context(
    *,
    trace_id: Optional[str] = None,
    span_name: str,
    phase: Optional[str] = None,
    parent_span_id: Optional[str] = None,
    **tag_kwargs: Any,
) -> Generator[TraceSpan, None, None]:
    """创建并管理一个 span 的生命周期。

    用法::

        with span_context(trace_id=tid, span_name="phase1", phase="phase1") as span:
            ...  # span 自动在退出时 close 并发射事件

    支持嵌套：内层 span 的 parent_span_id 和 trace_id 自动从外层继承。
    """
    current = get_current_span()
    effective_parent = parent_span_id or (current.span_id if current else None)
    effective_trace_id = trace_id or (current.trace_id if current else None)
    if effective_trace_id is None:
        raise ValueError("trace_id is required for the root span (or call inside an existing context)")

    # 从 tag_kwargs 中提取特殊字段
    extracted_phase = tag_kwargs.pop("_phase", None) or phase
    span = TraceSpan(
        trace_id=effective_trace_id,
        parent_span_id=effective_parent,
        name=span_name,
        phase=extracted_phase,
        tags=dict(tag_kwargs),
    )

    push_span(span)
    try:
        yield span
    except Exception:
        span.close(status=SpanStatus.ERROR)
        raise
    else:
        span.close()
    finally:
        pop_span()


# ── 工厂函数 ────────────────────────────────────────────────────


def create_trace_id() -> str:
    """生成新的 UUID4 格式 trace ID。"""
    return str(uuid.uuid4())
