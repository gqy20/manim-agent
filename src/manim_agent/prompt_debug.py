"""Prompt debug artifact writer for pipeline phase inspection."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


def prompt_debug_enabled() -> bool:
    value = os.environ.get("ENABLE_PROMPT_DEBUG", "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(k): _json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [_json_safe(v) for v in value]
        return str(value)


def _options_summary(options: Any, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    summary = {
        "max_turns": getattr(options, "max_turns", None),
        "allowed_tools": getattr(options, "allowed_tools", None),
        "disallowed_tools": getattr(options, "disallowed_tools", None),
        "tools": getattr(options, "tools", None),
        "cwd": getattr(options, "cwd", None),
        "permission_mode": getattr(options, "permission_mode", None),
        "session_id": getattr(options, "session_id", None),
    }
    output_format = getattr(options, "output_format", None)
    if isinstance(output_format, dict):
        summary["output_schema"] = output_format.get("name") or output_format.get("type")
    if overrides:
        summary.update(overrides)
    return _json_safe(summary)


def _approx_tokens(*texts: str | None) -> int:
    chars = sum(len(text or "") for text in texts)
    return max(1, chars // 4) if chars else 0


def write_prompt_artifact(
    *,
    output_dir: str,
    phase_id: str,
    phase_name: str,
    system_prompt: str | None = None,
    user_prompt: str | None = None,
    inputs: dict[str, Any] | None = None,
    options: Any = None,
    options_summary: dict[str, Any] | None = None,
    referenced_artifacts: dict[str, Any] | None = None,
    output_snapshot: dict[str, Any] | None = None,
    error: str | None = None,
) -> str | None:
    """Persist a phase prompt/debug snapshot when ENABLE_PROMPT_DEBUG is enabled."""
    if not prompt_debug_enabled():
        return None

    root = Path(output_dir).resolve()
    debug_dir = root / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)

    created_at = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())
    safe_phase_id = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in phase_id)
    artifact_path = debug_dir / f"{safe_phase_id}.prompt.json"
    system_text = system_prompt or ""
    user_text = user_prompt or ""

    payload = {
        "task_id": root.name,
        "phase_id": phase_id,
        "phase_name": phase_name,
        "created_at": created_at,
        "inputs": _json_safe(inputs or {}),
        "system_prompt": system_text,
        "user_prompt": user_text,
        "options": _options_summary(options, options_summary),
        "referenced_artifacts": _json_safe(referenced_artifacts or {}),
        "output_snapshot": _json_safe(output_snapshot or {}),
        "error": error,
        "metrics": {
            "system_prompt_chars": len(system_text),
            "user_prompt_chars": len(user_text),
            "approx_tokens": _approx_tokens(system_text, user_text),
        },
    }
    artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _update_prompt_index(debug_dir, payload, artifact_path)
    return str(artifact_path)


def _update_prompt_index(debug_dir: Path, payload: dict[str, Any], artifact_path: Path) -> None:
    index_path = debug_dir / "prompt_index.json"
    index: dict[str, Any] = {"task_id": payload["task_id"], "phases": []}
    if index_path.exists():
        try:
            existing = json.loads(index_path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                index = existing
        except json.JSONDecodeError:
            pass

    phase_summary = {
        "phase_id": payload["phase_id"],
        "phase_name": payload["phase_name"],
        "created_at": payload["created_at"],
        "artifact_path": str(artifact_path),
        "metrics": payload["metrics"],
        "error": payload["error"],
    }
    phases = [p for p in index.get("phases", []) if p.get("phase_id") != payload["phase_id"]]
    phases.append(phase_summary)
    index["phases"] = phases
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
