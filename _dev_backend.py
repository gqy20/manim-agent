"""Development entry point for the backend server.

Runs uvicorn with hot-reload while excluding pipeline output directories
from file watching (so SDK-generated files don't trigger spurious restarts).
"""

import subprocess
import sys


def main() -> None:
    host = "127.0.0.1"
    port = 8471
    # Collect extra args from command line (e.g. --port 9000)
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--host" and i + 1 < len(args):
            host = args[i + 1]
        elif a == "--port" and i + 1 < len(args):
            port = int(args[i + 1])

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        host,
        "--port",
        str(port),
        "--reload",
        "--reload-exclude",
        "backend/output/*",
        "--reload-exclude",
        "backend/data/*",
    ]
    subprocess.run(cmd)


if __name__ == "__main__":
    main()
