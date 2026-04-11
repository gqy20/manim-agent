"""SDK hook callbacks and per-pipeline hook state."""

from __future__ import annotations

import contextvars
import logging
from dataclasses import dataclass, field
from typing import Any

from claude_agent_sdk.types import PostToolUseHookSpecificOutput, SyncHookJSONOutput

logger = logging.getLogger(__name__)


@dataclass
class _HookState:
    """Hook state scoped to a single pipeline execution."""

    captured_source_code: dict[str, str] = field(default_factory=dict)
    event_callback: Any = None


_hook_state_var: contextvars.ContextVar[_HookState | None] = contextvars.ContextVar(
    "manim_agent_hook_state",
    default=None,
)


def create_hook_state(
    *,
    event_callback: Any = None,
) -> _HookState:
    """Create a fresh hook state for one pipeline run."""
    state = _HookState()
    state.event_callback = event_callback
    return state


def get_hook_state() -> _HookState:
    """Return the current hook state, creating one lazily when needed."""
    state = _hook_state_var.get()
    if state is None:
        state = _HookState()
        _hook_state_var.set(state)
    return state


def activate_hook_state(state: _HookState | None = None) -> contextvars.Token:
    """Bind a hook state to the current async context."""
    return _hook_state_var.set(state or _HookState())


def reset_hook_state(token: contextvars.Token) -> None:
    """Restore the previous hook state binding."""
    _hook_state_var.reset(token)


class _HookStateProxy:
    """Backward-compatible proxy for code that still imports _hook_state."""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_hook_state(), name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(get_hook_state(), name, value)


_hook_state = _HookStateProxy()


async def _on_post_tool_use(
    input_data,
    tool_use_id: str | None,
    context,
) -> SyncHookJSONOutput:
    """Capture Python source written via Write/Edit tools."""
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    hook_state = get_hook_state()

    logger.debug(
        "PostToolUse: tool_name=%r, tool_use_id=%r",
        tool_name,
        tool_use_id,
    )

    if tool_name in ("Write", "Edit") and isinstance(tool_input, dict):
        file_path = tool_input.get("file_path", "")
        content = tool_input.get("content", "")
        logger.debug(
            "PostToolUse: %s file_path=%r, content_length=%s",
            tool_name,
            file_path,
            len(content) if content else 0,
        )
        if file_path.endswith(".py") and content:
            hook_state.captured_source_code[file_path] = content
            logger.debug(
                "Captured source: %s, total_files=%d",
                file_path,
                len(hook_state.captured_source_code),
            )
    elif tool_name:
        logger.debug("PostToolUse: skipping non-target tool: %s", tool_name)

    return SyncHookJSONOutput(
        hookSpecificOutput=PostToolUseHookSpecificOutput(
            hookEventName="PostToolUse",
        )
    )
