"""Development launcher — starts uvicorn with reload excludes configured programmatically.

Avoids Windows shell glob expansion issues with --reload-exclude CLI argument.
"""

import os
import sys

# Ensure project root is on sys.path for the parent process import.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Also set PYTHONPATH so uvicorn's reloader subprocess (spawned via
# multiprocessing on Windows) can resolve "backend.main".
_existing = os.environ.get("PYTHONPATH", "")
_prefix = _PROJECT_ROOT if not _existing else f"{_PROJECT_ROOT}{os.pathsep}{_existing}"
os.environ["PYTHONPATH"] = _prefix

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8471,
        reload=True,
        # Exclude pipeline output directories from hot-reload watching.
        # These are written by the Claude Agent SDK subprocess and must NOT
        # trigger a server restart mid-pipeline.
        #
        # IMPORTANT: Use real directory paths (no globs) so uvicorn's
        # FileFilter routes them into exclude_dirs (checked via
        # path.parents containment) rather than exclude_patterns (which
        # use Path.match() and fail on Windows due to / vs \).
        reload_excludes=[
            "backend/output",
            "backend/data",
            ".venv",
            "node_modules",
            ".next",
        ],
    )
