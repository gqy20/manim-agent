"""Shared filesystem paths for the backend runtime."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_OUTPUT_ROOT = PROJECT_ROOT / "backend" / "output"
BACKEND_LOG_ROOT = PROJECT_ROOT / "backend" / "logs"
