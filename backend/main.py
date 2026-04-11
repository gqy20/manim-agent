"""FastAPI application entry point for manim-agent web backend."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from anyio import BrokenResourceError
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from .routes import router, set_store
from .task_store import TaskStore

# ── 日志文件配置 ───────────────────────────────────────────────
_log_dir = Path("backend/logs")
_log_dir.mkdir(exist_ok=True)
_log_file = _log_dir / f"manim-agent-{os.getpid()}.log"

# 基础配置：同时输出到文件和控制台
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(_log_file, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class _SSEDisconnectMiddleware(BaseHTTPMiddleware):
    """Suppress benign SSE disconnect errors when clients close connections.

    When SSE clients disconnect, Starlette's EventSourceResponse raises
    BrokenResourceError (sometimes wrapped in ExceptionGroup). This is normal
    and should not surface as ERROR-level server logs.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            return await call_next(request)
        except ExceptionGroup as exc:
            # If *all* sub-exceptions are BrokenResourceError, suppress silently.
            broken = exc.subgroup(BrokenResourceError)
            if broken is not None and len(broken.exceptions) == len(exc.exceptions):
                return Response(status_code=204)
            raise
        except BrokenResourceError:
            return Response(status_code=204)


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = TaskStore()
    set_store(store)
    app.state.store = store
    # 启动横幅：让用户在终端中一眼识别后端就绪状态
    print()
    print("=" * 56)
    print("  Manim Agent Backend Ready")
    print(f"  Tasks in store: {len(store._tasks)}")
    print(f"  Output dir:   {Path('backend/output').resolve()}")
    print("=" * 56)
    print()
    yield
    await store.save()


app = FastAPI(
    title="Manim Agent API",
    description="Web API for AI-driven Manim math animation generation",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3147"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Suppress benign SSE disconnect errors (BrokenResourceError from keepalive)
app.add_middleware(_SSEDisconnectMiddleware)

app.include_router(router)

# Serve generated videos as static files
output_dir = Path("backend/output")
if output_dir.exists():
    app.mount("/videos", StaticFiles(directory=str(output_dir)), name="videos")


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
