"""Pipeline configuration: SDK options builder, stderr handler, path helpers.

Re-exports from runtime_options plus pipeline-specific helpers.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from .dispatcher import _EMOJI
from .pipeline_events import EventType, PhaseBoundaryPayload, PipelineEvent, StatusPayload
from .runtime_options import (
    build_options as _runtime_build_options,
)
from .runtime_options import (
    get_local_plugins,
    select_permission_mode,
)
from .runtime_options import (
    resolve_plugin_dir as _resolve_plugin_dir_runtime,
)
from .runtime_options import (
    resolve_repo_root as _resolve_repo_root_runtime,
)

__all__ = [
    "build_options",
    "emit_status",
    "emit_phase_enter",
    "emit_phase_exit",
    "get_local_plugins",
    "resolve_plugin_dir",
    "resolve_repo_root",
    "select_permission_mode",
    "stderr_handler",
]


def resolve_repo_root(cwd: str | None = None) -> Path:
    return _resolve_repo_root_runtime(cwd)


def resolve_plugin_dir(cwd: str | None = None) -> Path:
    return _resolve_plugin_dir_runtime(cwd)


def stderr_handler(
    line: str,
    *,
    log_callback: Callable[[str], None] | None = None,
) -> None:
    """Forward CLI stderr to SSE callback and mirror errors to stderr."""
    stripped = line.strip()
    if log_callback is not None:
        log_callback(f"[CLI] {stripped}")
    lower = line.lower()
    if any(kw in lower for kw in ("error", "warning", "fail", "exception")):
        print(f"  {_EMOJI['cross']} [CLI] {stripped}", file=sys.stderr)


def build_options(
    cwd: str,
    system_prompt: str | None,
    max_turns: int,
    *,
    prompt_file: str | None = None,
    quality: str = "high",
    log_callback: Callable[[str], None] | None = None,
    output_format: dict[str, Any] | None = None,
    use_default_output_format: bool = True,
    tools: list[str] | None = None,
    allowed_tools: list[str] | None = None,
    disallowed_tools: list[str] | None = None,
    skills: list[str] | Literal["all"] | None = None,
) -> Any:
    """Build ClaudeAgentOptions, forwarding to runtime_options.build_options."""
    return _runtime_build_options(
        cwd=cwd,
        system_prompt=system_prompt,
        max_turns=max_turns,
        prompt_file=prompt_file,
        quality=quality,
        log_callback=log_callback,
        output_format=output_format,
        use_default_output_format=use_default_output_format,
        tools=tools,
        allowed_tools=allowed_tools,
        disallowed_tools=disallowed_tools,
        skills=skills,
        error_prefix=_EMOJI["cross"],
    )


def emit_status(
    event_callback: Callable[[PipelineEvent], None] | None,
    *,
    task_status: str,
    phase: str | None = None,
    message: str | None = None,
    pipeline_output: dict[str, Any] | None = None,
) -> None:
    """Emit a structured status event when an SSE callback is available."""
    if event_callback is None:
        return
    event_callback(
        PipelineEvent(
            event_type=EventType.STATUS,
            data=StatusPayload(
                task_status=task_status,
                phase=phase,
                message=message,
                pipeline_output=pipeline_output,
            ),
        )
    )


# ── Phase 边界事件（成对 enter/exit）────────────────────────────

_phase_enter_times: dict[str, int] = {}


def emit_phase_enter(
    event_callback: Callable[[PipelineEvent], None] | None,
    *,
    phase_id: str,
    phase_name: str,
    trace_id: str | None = None,
) -> None:
    """发射 PHASE_ENTER 事件，记录进入时间用于后续 exit 计算 duration。"""
    if event_callback is None:
        return
    import time as _t
    _phase_enter_times[phase_id] = int(_t.time() * 1000)
    event_callback(
        PipelineEvent(
            event_type=EventType.PHASE_BOUNDARY,
            data=PhaseBoundaryPayload(
                action="enter",
                phase_id=phase_id,
                phase_name=phase_name,
                trace_id=trace_id,
            ),
        )
    )


def emit_phase_exit(
    event_callback: Callable[[PipelineEvent], None] | None,
    *,
    phase_id: str,
    phase_name: str,
    status: str = "ok",
    turn_count: int | None = None,
    beats_count: int | None = None,
    trace_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """发射 PHASE_EXIT 事件，自动计算 duration_ms。"""
    if event_callback is None:
        return
    import time as _t
    now_ms = int(_t.time() * 1000)
    start_ms = _phase_enter_times.pop(phase_id, now_ms)
    duration = max(0, now_ms - start_ms)
    event_callback(
        PipelineEvent(
            event_type=EventType.PHASE_BOUNDARY,
            data=PhaseBoundaryPayload(
                action="exit",
                phase_id=phase_id,
                phase_name=phase_name,
                trace_id=trace_id,
                duration_ms=duration,
                status=status,
                turn_count=turn_count,
                beats_count=beats_count,
                metadata=metadata or {},
            ),
        )
    )
