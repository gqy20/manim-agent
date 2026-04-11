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
        port=int(os.environ.get("BE_PORT", "8471")),
        reload=True,
        # Watch only source directories so generated task output cannot trigger
        # a backend restart in the middle of a Claude run.
        reload_dirs=[
            os.path.join(_PROJECT_ROOT, "backend"),
            os.path.join(_PROJECT_ROOT, "src"),
        ],
        reload_excludes=[
            os.path.join(_PROJECT_ROOT, "backend", "output"),
            os.path.join(_PROJECT_ROOT, "backend", "data"),
            os.path.join(_PROJECT_ROOT, ".venv"),
            os.path.join(_PROJECT_ROOT, "frontend", ".next"),
            os.path.join(_PROJECT_ROOT, "node_modules"),
        ],
    )
