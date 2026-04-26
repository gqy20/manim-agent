"""SDK hook callbacks and per-pipeline hook state."""

from __future__ import annotations

import contextvars
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from claude_agent_sdk.types import (
    PostToolUseFailureHookSpecificOutput,
    PostToolUseHookSpecificOutput,
    PreToolUseHookSpecificOutput,
    SyncHookJSONOutput,
)

from .repo_paths import resolve_repo_root

logger = logging.getLogger(__name__)


def _plugin_readonly_dirs(cwd: str | None = None) -> tuple[Path, ...]:
    return (resolve_repo_root(cwd) / "plugins",)


def normalize_path_string(path_str: str) -> str:
    """Normalize SDK-reported paths across shells and platforms."""
    text = path_str.strip()
    if not text:
        return text

    if re.match(r"^/[a-zA-Z]/", text):
        drive = text[1].upper()
        remainder = text[2:].lstrip("/").replace("/", "\\")
        text = f"{drive}:\\{remainder}"

    try:
        return str(Path(text).resolve())
    except OSError:
        return text


def _is_within_directory(path_str: str, cwd: str) -> bool:
    normalized_path = normalize_path_string(path_str)
    normalized_cwd = normalize_path_string(cwd)
    if not normalized_path or not normalized_cwd:
        return False

    try:
        Path(normalized_path).resolve().relative_to(Path(normalized_cwd).resolve())
        return True
    except ValueError:
        return False


def _is_within_any_directory(path_str: str, roots: tuple[Path, ...]) -> bool:
    normalized_path = normalize_path_string(path_str)
    if not normalized_path:
        return False

    try:
        resolved_path = Path(normalized_path).resolve()
    except OSError:
        return False

    for root in roots:
        try:
            resolved_path.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


def _bash_contains_out_of_scope_path(command: str, cwd: str) -> str | None:
    patterns = [
        r"([A-Za-z]:[\\/][^\s`\"']+)",
        r"(/[^`\s\"']+)",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, command):
            normalized = normalize_path_string(match.rstrip(".,)"))
            if not normalized:
                continue
            # Only enforce paths that point into the same repository tree but
            # escape the per-task working directory.
            if "manim-agent" in normalized.lower() and not _is_within_directory(
                normalized, cwd
            ):
                return normalized
    return None


def _write_scope_denial(file_path: str) -> str:
    normalized = normalize_path_string(file_path)
    basename = Path(normalized).name or "scene.py"
    suggested_name = "scene.py" if normalized.endswith(".py") else basename
    return (
        "Only files inside the task directory are allowed. "
        f"Rejected path: {normalized}. "
        f"Retry with a relative path inside the task directory, for example `{suggested_name}`."
    )


def _read_scope_denial(file_path: str) -> str:
    normalized = normalize_path_string(file_path)
    basename = Path(normalized).name or "reference.md"
    return (
        "Read access is limited to the task directory and approved local plugin references. "
        f"Rejected path: {normalized}. "
        f"Retry with a path inside the task directory or an approved plugin reference such as `{basename}`."
    )


def _bash_scope_denial(escaped_path: str) -> str:
    return (
        "Bash commands must stay inside the task directory. "
        f"Rejected path: {escaped_path}. "
        "Retry from the current task directory and run Manim directly, for example "
        "`manim -qh scene.py GeneratedScene`. "
        "Do not cd to the repository root and do not invoke `.venv/Scripts/python`."
    )


@dataclass
class _HookState:
    """Hook state scoped to a single pipeline execution."""

    captured_source_code: dict[str, str] = field(default_factory=dict)
    event_callback: Any = None
    allowed_tools: set[str] | None = None


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


async def _on_pre_tool_use(
    input_data,
    tool_use_id: str | None,
    context,
) -> SyncHookJSONOutput:
    """Block tool calls that escape the per-task working directory."""
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    cwd = input_data.get("cwd", "")
    hook_state = get_hook_state()

    deny_reason: str | None = None
    if hook_state.allowed_tools is not None and tool_name not in hook_state.allowed_tools:
        allowed = ", ".join(sorted(hook_state.allowed_tools))
        deny_reason = (
            f"Tool `{tool_name}` is not allowed in this phase. "
            f"Allowed tools: {allowed}."
        )
    if deny_reason is None and tool_name == "Read" and isinstance(tool_input, dict):
        file_path = tool_input.get("file_path", "")
        if (
            file_path
            and not _is_within_directory(file_path, cwd)
            and not _is_within_any_directory(file_path, _plugin_readonly_dirs(cwd))
        ):
            deny_reason = _read_scope_denial(file_path)
    elif deny_reason is None and tool_name in ("Write", "Edit") and isinstance(tool_input, dict):
        file_path = tool_input.get("file_path", "")
        if file_path and not _is_within_directory(file_path, cwd):
            deny_reason = _write_scope_denial(file_path)
    elif deny_reason is None and tool_name == "Bash" and isinstance(tool_input, dict):
        command = tool_input.get("command", "")
        escaped_path = _bash_contains_out_of_scope_path(command, cwd)
        if escaped_path:
            deny_reason = _bash_scope_denial(escaped_path)

    if deny_reason is None:
        return SyncHookJSONOutput(
            hookSpecificOutput=PreToolUseHookSpecificOutput(
                hookEventName="PreToolUse",
                permissionDecision="allow",
            )
        )

    logger.warning("PreToolUse denied %s: %s", tool_name, deny_reason)
    return SyncHookJSONOutput(
        decision="block",
        reason=deny_reason,
        hookSpecificOutput=PreToolUseHookSpecificOutput(
            hookEventName="PreToolUse",
            permissionDecision="deny",
            permissionDecisionReason=deny_reason,
        ),
    )


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
        normalized_path = normalize_path_string(file_path)
        logger.debug(
            "PostToolUse: %s file_path=%r normalized=%r content_length=%s",
            tool_name, file_path, normalized_path, len(content) if content else 0,
        )
        if file_path.endswith(".py") and content:
            hook_state.captured_source_code[normalized_path] = content
            logger.debug(
                "Captured source: %s, total_files=%d",
                normalized_path,
                len(hook_state.captured_source_code),
            )
    elif tool_name:
        logger.debug("PostToolUse: skipping non-target tool: %s", tool_name)

    return SyncHookJSONOutput(
        hookSpecificOutput=PostToolUseHookSpecificOutput(
            hookEventName="PostToolUse",
        )
    )


async def _on_post_tool_use_failure(
    input_data,
    tool_use_id: str | None,
    context,
) -> SyncHookJSONOutput:
    """捕获工具执行失败信息，注入到 dispatcher 的错误分类记录中。

    error_type 分类：
      - "execution"：命令执行失败（非零退出码）
      - "permission"：权限拒绝（路径越权等）
      - "timeout"：执行超时
      - "interrupt"：用户中断
    """
    tool_name = input_data.get("tool_name", "")
    error_msg = input_data.get("error", "") or ""
    tool_input = input_data.get("tool_input", {})
    hook_state = get_hook_state()

    logger.debug(
        "PostToolUseFailure: tool_name=%r, tool_use_id=%r, error=%r",
        tool_name, tool_use_id, error_msg[:200],
    )

    # 推断 error_type
    error_type = "execution"
    if not error_type and "timeout" in str(error_msg).lower():
        error_type = "timeout"
    if not error_type and "interrupt" in str(error_msg).lower():
        error_type = "interrupt"

    # 通过 hook_state 传递给 dispatcher
    # （dispatcher 在同一 async context 中可通过 get_hook_state() 获取）
    if tool_use_id and hasattr(hook_state, "_tool_failures"):
        hook_state._tool_failures[tool_use_id] = (error_type, error_msg[:500])

    return SyncHookJSONOutput(
        hookSpecificOutput=PostToolUseFailureHookSpecificOutput(
            hookEventName="PostToolUseFailure",
        ),
    )
