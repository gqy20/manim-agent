"""Development launcher — starts uvicorn with reload excludes configured programmatically.

Avoids Windows shell glob expansion issues with --reload-exclude CLI argument.
"""

import os
import sys

# Ensure project root is on sys.path for the parent process import.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC_ROOT = os.path.join(_PROJECT_ROOT, "src")
for _path in (_PROJECT_ROOT, _SRC_ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

# Also set PYTHONPATH so uvicorn's reloader subprocess (spawned via
# multiprocessing on Windows) can resolve "backend.main" and the src-layout
# "manim_agent" package.
_existing = os.environ.get("PYTHONPATH", "")
_prefix_parts = [_PROJECT_ROOT, _SRC_ROOT]
if _existing:
    _prefix_parts.append(_existing)
_prefix = os.pathsep.join(_prefix_parts)
os.environ["PYTHONPATH"] = _prefix

import uvicorn  # noqa: E402 - sys.path/PYTHONPATH must be patched before uvicorn starts.

if __name__ == "__main__":
    reload_flag = os.environ.get("RELOAD", "false").lower() in {"1", "true", "yes", "on"}
    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=int(os.environ.get("BE_PORT", "8471")),
        reload=reload_flag,
        # Watch only source directories so generated task output cannot trigger
        # a backend restart in the middle of a Claude run.
        reload_dirs=[
            os.path.join(_PROJECT_ROOT, "backend"),
            os.path.join(_PROJECT_ROOT, "src"),
        ],
        # Use relative patterns — Windows pathlib.glob() rejects absolute paths.
        reload_excludes=[
            "backend/output",
            ".venv",
            "frontend/.next",
            "node_modules",
        ],
    )
