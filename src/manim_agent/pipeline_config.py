"""Pipeline configuration: SDK options builder, stderr handler, path helpers.

Re-exports from runtime_options plus pipeline-specific helpers.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .dispatcher import _EMOJI
from .pipeline_events import EventType, PipelineEvent, StatusPayload
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
    allowed_tools: list[str] | None = None,
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
        allowed_tools=allowed_tools,
        error_prefix=_EMOJI["cross"],
    )


def emit_status(
    event_callback: Callable[[PipelineEvent], None] | None,
    *,
    task_status: str,
    phase: str | None = None,
    message: str | None = None,
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
            ),
        )
    )
