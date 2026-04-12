"""Shared repository path helpers for local and installed runtimes."""

from __future__ import annotations

import os
from pathlib import Path


def resolve_repo_root(cwd: str | None = None) -> Path:
    """Best-effort repo root discovery for both editable and installed layouts."""
    marker_options = (
        ("plugins", "manim-production", ".claude-plugin", "plugin.json"),
        ("plugins", "manim-production", ".codex-plugin", "plugin.json"),
    )
    candidates: list[Path] = []

    env_root = os.environ.get("MANIM_AGENT_REPO_ROOT")
    if env_root:
        candidates.append(Path(env_root).resolve())

    if cwd:
        resolved_cwd = Path(cwd).resolve()
        candidates.extend([resolved_cwd, *resolved_cwd.parents])

    module_path = Path(__file__).resolve()
    candidates.extend(module_path.parents)

    for candidate in candidates:
        for marker_parts in marker_options:
            if (candidate / Path(*marker_parts)).exists():
                return candidate

    return module_path.parents[2]


def resolve_plugin_dir(cwd: str | None = None) -> Path:
    """Return the repo-local manim-production plugin directory."""
    return resolve_repo_root(cwd) / "plugins" / "manim-production"
