"""Pipeline integration adapter for automatic layout safety auditing.

Runs layout_safety.py as a subprocess (isolated Manim environment) after
Phase 2B completes, parses results into structured data, persists a debug
artifact JSON, and returns a LayoutAuditResult for pipeline consumption.
"""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_LAYOUT_SAFETY_SCRIPT = (
    Path(__file__).resolve().parent.parent.parent
    / "plugins"
    / "manim-production"
    / "skills"
    / "layout-safety"
    / "scripts"
    / "layout_safety.py"
)

_AUDIT_TIMEOUT_SECONDS = 60

_BLOCKING_KINDS = frozenset({"overlap-refined", "frame-overflow"})


@dataclass
class LayoutAuditResult:
    """Structured result of an automatic pipeline layout audit."""

    ran: bool = False
    exit_code: int = -1
    checked_mobject_count: int = 0
    issues: list[dict[str, object]] = field(default_factory=list)
    summary: str = ""
    artifact_path: str | None = None
    blocking: bool = False


def _parse_audit_stdout(stdout: str) -> LayoutAuditResult:
    """Parse layout_safety.py stdout into a structured result."""
    lines = stdout.strip().splitlines()
    result = LayoutAuditResult(ran=True)
    issues: list[dict[str, object]] = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Checkpoint header: [label] summary text
        if line.startswith("[") and "]" in line:
            if result.summary:
                result.summary += "; " + line
            else:
                result.summary = line
            continue

        # Issue line: starts with "  - "
        if line.startswith("- ") or line.startswith("  - "):
            message = line.lstrip("- ").strip()
            issue = _classify_issue_from_message(message)
            issues.append(issue)
            continue

        # Summary line containing "checked" or "issues"
        if "checked" in line.lower() or "issue" in line.lower():
            if not result.summary:
                result.summary = line

    result.issues = issues
    result.blocking = any(
        iss.get("kind") in _BLOCKING_KINDS for iss in issues
    )

    # Extract checked count from summary if available
    import re
    count_match = re.search(r"checked\s+(\d+)", result.summary)
    if count_match:
        result.checked_mobject_count = int(count_match.group(1))

    return result


def _classify_issue_from_message(message: str) -> dict[str, object]:
    """Infer issue kind from the message text."""
    kind = "overlap"
    if "refined" in message.lower() and ("overlap" in message.lower()):
        kind = "overlap-refined"
    elif "false-positive" in message.lower():
        kind = "overlap-false-positive"
    elif "crowding" in message.lower():
        kind = "crowding"
    elif "overflow" in message.lower() or "off_screen" in message.lower():
        kind = "frame-overflow"

    subjects: list[str] = []
    # Try to extract subject names like "Text[1] overlaps MathTex[3]"
    overlap_match = message.split(" overlaps ")
    if len(overlap_match) >= 2:
        subjects.append(overlap_match[0].strip().split()[-1] if overlap_match[0].strip() else "")
        second = overlap_match[1].split("(")[0].strip() if "(" in overlap_match[1] else overlap_match[1]
        subjects.append(second)
    elif " vs " in message:
        parts = message.split(" vs ", 1)
        subjects.append(parts[0].strip().split()[-1] if parts[0].strip() else "")
        subjects.append(parts[1].split(":")[0].strip() if ":" in parts[1] else parts[1].strip())
    elif "exceeds" in message.lower() or "crowded" in message.lower():
        first_word = message.split()[0] if message.split() else ""
        subjects.append(first_word)

    return {
        "kind": kind,
        "message": message,
        "subjects": [s for s in subjects if s],
    }


def _persist_audit_artifact(
    *,
    output_dir: str,
    exit_code: int,
    stdout: str,
    stderr: str,
    parsed: LayoutAuditResult,
) -> str | None:
    """Write layout audit results to a debug artifact JSON file."""
    try:
        out_path = Path(output_dir) / "debug" / "layout_audit.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "ran": True,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr[:5000] if stderr else "",
            "parsed": {
                "checked_mobject_count": parsed.checked_mobject_count,
                "issue_count": len(parsed.issues),
                "issues": parsed.issues,
                "summary": parsed.summary,
                "blocking": parsed.blocking,
            },
        }
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(out_path.resolve())
    except Exception:
        logger.exception("Failed to persist layout audit artifact")
        return None


def run_layout_audit_pipeline(
    *,
    scene_file: str | None,
    scene_class: str | None,
    output_dir: str,
    log_callback: Callable[[str], None] | None = None,
) -> LayoutAuditResult:
    """Execute layout safety audit automatically within the pipeline flow.

    Called after Phase 2B completes and before Phase 3 render review.
    Uses subprocess to isolate Manim's global config from the pipeline process.
    """
    _log = log_callback or (lambda msg: None)

    if not scene_file:
        _log("[LAYOUT] Skipped: no scene_file available")
        return LayoutAuditResult(ran=False, summary="no scene_file available")

    script_path = _resolve_scene_path(scene_file, output_dir)
    if script_path is None or not script_path.exists():
        _log(f"[LAYOUT] Skipped: scene file not found at {scene_file}")
        return LayoutAuditResult(
            ran=False,
            summary=f"scene file not found: {scene_file}",
        )

    scene_cls = scene_class or "GeneratedScene"
    safety_script = _LAYOUT_SAFETY_SCRIPT
    if not safety_script.exists():
        _log(f"[LAYOUT] Skipped: layout_safety.py not found at {safety_script}")
        return LayoutAuditResult(
            ran=False,
            summary="layout_safety.py script not found",
        )

    cmd = [
        "python",
        str(safety_script),
        str(script_path),
        scene_cls,
        "--checkpoint-mode",
        "after-play",
    ]

    _log(f"[LAYOUT] Running audit: {' '.join(cmd)}")
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_AUDIT_TIMEOUT_SECONDS,
            cwd=str(Path(output_dir).resolve()),
        )
    except subprocess.TimeoutExpired:
        _log(f"[LAYOUT] ERROR: timed out after {_AUDIT_TIMEOUT_SECONDS}s")
        return LayoutAuditResult(
            ran=True,
            exit_code=124,
            summary=f"audit timed out after {_AUDIT_TIMEOUT_SECONDS}s",
        )
    except FileNotFoundError:
        _log("[LAYOUT] ERROR: python executable not found")
        return LayoutAuditResult(
            ran=False,
            summary="python executable not found",
        )
    except Exception as exc:
        _log(f"[LAYOUT] ERROR: {exc}")
        return LayoutAuditResult(
            ran=True,
            exit_code=2,
            summary=f"audit failed: {exc}",
        )

    exit_code = proc.returncode
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""

    if exit_code == 0:
        _log(f"[LAYOUT] OK: {stdout.strip().split(chr(10))[0] if stdout else 'clean'}")
    elif exit_code == 1:
        _log(f"[LAYOUT] ISSUES FOUND ({len(stdout.strip().splitlines())} lines)")
    else:
        _log(f"[LAYOUT] ERROR (exit={exit_code}): {(stderr or stdout)[:200]}")

    parsed = _parse_audit_stdout(stdout)
    parsed.exit_code = exit_code

    # Persist debug artifact
    artifact = _persist_audit_artifact(
        output_dir=output_dir,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        parsed=parsed,
    )
    parsed.artifact_path = artifact

    return parsed


def _resolve_scene_path(scene_file: str, output_dir: str) -> Path | None:
    """Resolve scene_file to an absolute path, checking both as-is and relative to output_dir."""
    p = Path(scene_file)
    if p.is_absolute() and p.exists():
        return p
    relative = Path(output_dir).resolve() / p
    if relative.exists():
        return relative
    return None
