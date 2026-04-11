"""FastAPI application entry point for manim-agent web backend."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from anyio import BrokenResourceError
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

from .routes import router, set_store, init_r2_client
from .task_store import TaskStore

# ── 日志文件配置 ───────────────────────────────────────────────
_log_dir = Path("backend/logs")
_log_dir.mkdir(exist_ok=True)
_log_file = _log_dir / f"manim-agent-{os.getpid()}.log"

# 基础配置：同时输出到文件和控制台
_log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(_log_file, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def _is_benign_sse_disconnect(exc: BaseException) -> bool:
    """Return True when the exception only contains SSE disconnect errors."""
    if isinstance(exc, BrokenResourceError):
        return True
    if isinstance(exc, ExceptionGroup):
        return all(
            _is_benign_sse_disconnect(child) for child in exc.exceptions
        )
    return False


class _SSEDisconnectMiddleware:
    """Suppress benign SSE disconnect errors when clients close connections.

    When SSE clients disconnect, Starlette's EventSourceResponse raises
    BrokenResourceError (sometimes wrapped in ExceptionGroup). This is normal
    and should not surface as ERROR-level server logs.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        try:
            await self.app(scope, receive, send)
        except BaseException as exc:
            if _is_benign_sse_disconnect(exc):
                logger.debug(
                    "Suppressing benign SSE disconnect: %s",
                    type(exc).__name__,
                )
                return
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = TaskStore()
    await store.start()
    set_store(store)
    app.state.store = store

    # Initialize R2 storage client (no-op if not configured)
    init_r2_client()

    # Query task count from DB for startup banner
    try:
        count = len(await store.list_all(limit=9999))
    except Exception:
        count = 0

    r2_mode = "R2 (cloud)" if _r2_client else "Local filesystem"
    # 启动横幅：让用户在终端中一眼识别后端就绪状态
    print()
    print("=" * 56)
    print("  Manim Agent Backend Ready")
    print(f"  Tasks in DB:   {count}")
    print(f"  Storage:      {r2_mode}")
    print(f"  Output dir:   {Path('backend/output').resolve()}")
    print("=" * 56)
    print()
    yield
    await store.close()


app = FastAPI(
    title="Manim Agent API",
    description="Web API for AI-driven Manim math animation generation",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
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
