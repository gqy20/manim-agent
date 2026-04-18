"""Runtime option and local plugin helpers for the Manim agent."""

from __future__ import annotations

import functools
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

from . import prompts
from .hooks import _on_post_tool_use, _on_pre_tool_use
from .schemas import PipelineOutput
from .repo_paths import resolve_plugin_dir, resolve_repo_root

logger = logging.getLogger(__name__)


def get_local_plugins(cwd: str | None = None) -> list[dict[str, str]]:
    """Return repo-local Claude plugins that should be injected into every task."""
    plugin_dir = resolve_plugin_dir(cwd)
    manifest_paths = [
        plugin_dir / ".claude-plugin" / "plugin.json",
        plugin_dir / ".codex-plugin" / "plugin.json",
    ]
    for manifest_path in manifest_paths:
        if manifest_path.exists():
            return [{"type": "local", "path": str(plugin_dir)}]

    logger.warning("Local plugin manifest not found: %s", manifest_paths)
    return []


def select_permission_mode() -> str:
    """Choose a Claude Code permission mode that works in the current runtime."""
    geteuid = getattr(os, "geteuid", None)
    try:
        is_root = callable(geteuid) and geteuid() == 0
    except OSError:
        is_root = False

    if is_root:
        return "auto"
    return "bypassPermissions"


def stderr_handler(
    line: str,
    *,
    log_callback: Callable[[str], None] | None = None,
    error_prefix: str,
) -> None:
    """Forward CLI stderr to SSE and mirror important lines to stderr."""
    stripped = line.strip()
    if log_callback is not None:
        log_callback(f"[CLI] {stripped}")
    lower = line.lower()
    if any(kw in lower for kw in ("error", "warning", "fail", "exception")):
        print(f"  {error_prefix} [CLI] {stripped}", file=sys.stderr)


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
    error_prefix: str,
) -> ClaudeAgentOptions:
    """Build ClaudeAgentOptions with session isolation and local plugin injection."""
    resolved_cwd = str(Path(cwd).resolve())

    if prompt_file and Path(prompt_file).exists():
        final_system_prompt = Path(prompt_file).read_text(encoding="utf-8")
    elif system_prompt:
        final_system_prompt = system_prompt
    else:
        final_system_prompt = prompts.SYSTEM_PROMPT.replace(
            "-qh", prompts.QUALITY_FLAGS.get(quality, "-qh")
        )

    bound_stderr = functools.partial(
        stderr_handler,
        log_callback=log_callback,
        error_prefix=error_prefix,
    )

    repo_root = resolve_repo_root(resolved_cwd)
    venv_bin_dir = repo_root / ".venv" / ("Scripts" if os.name == "nt" else "bin")
    venv_scripts = str(venv_bin_dir)
    current_path = os.environ.get("PATH", "")
    path_parts = [p for p in current_path.split(os.pathsep) if p]
    if venv_scripts not in path_parts:
        path_parts.append(venv_scripts)
    venv_env = dict(os.environ)
    venv_env["PATH"] = os.pathsep.join(path_parts)

    hooks = {
        "PreToolUse": [
            HookMatcher(matcher="Read|Write|Edit|Bash", hooks=[_on_pre_tool_use]),
        ],
        "PostToolUse": [
            HookMatcher(matcher="Write|Edit", hooks=[_on_post_tool_use]),
        ],
    }

    permission_mode = select_permission_mode()
    resolved_allowed_tools = (
        allowed_tools
        if allowed_tools is not None
        else [
            "Read",
            "Write",
            "Edit",
            "Bash",
            "Glob",
            "Grep",
        ]
    )

    plugin_dir = resolve_plugin_dir(resolved_cwd)

    options = ClaudeAgentOptions(
        cwd=resolved_cwd,
        add_dirs=[resolved_cwd, str(plugin_dir)],
        system_prompt=final_system_prompt,
        permission_mode=permission_mode,
        max_turns=max_turns,
        session_id=str(uuid.uuid4()),
        fork_session=True,
        stderr=bound_stderr,
        output_format=(
            output_format
            if output_format is not None
            else (PipelineOutput.output_format_schema() if use_default_output_format else None)
        ),
        allowed_tools=resolved_allowed_tools,
        extra_args={"bare": None},
        env=venv_env,
        hooks=hooks,
        plugins=get_local_plugins(resolved_cwd),
        enable_file_checkpointing=True,
    )

    logger.debug(
        "_build_options: cwd=%s, max_turns=%s, permission_mode=%s, "
        "allowed_tools=%s, output_format=%s, fork_session=%s, "
        "enable_file_checkpointing%s, hooks=%s, system_prompt_length=%d",
        options.cwd,
        options.max_turns,
        options.permission_mode,
        options.allowed_tools,
        "set" if options.output_format else "None",
        options.fork_session,
        options.enable_file_checkpointing,
        list(options.hooks.keys()) if options.hooks else [],
        len(final_system_prompt) if final_system_prompt else 0,
    )
    logger.debug(
        "_build_options: cwd=%s, max_turns=%s, permission_mode=%s, "
        "allowed_tools=%s, plugins=%s, output_format=%s, system_prompt_len=%d",
        resolved_cwd,
        max_turns,
        permission_mode,
        options.allowed_tools,
        [plugin["path"] for plugin in options.plugins],
        "set" if options.output_format else "None",
        len(final_system_prompt) if final_system_prompt else 0,
    )
    return options
