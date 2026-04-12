"""FastAPI application entry point for manim-agent web backend."""

import logging
import os
from contextlib import asynccontextmanager
from logging import FileHandler, StreamHandler
from pathlib import Path

import httpx
from anyio import BrokenResourceError
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send
from dotenv import load_dotenv

from .routes import router, set_store, init_r2_client, _r2_client
from .task_store import TaskStore

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# ── Next.js upstream config ────────────────────────────────────
_NEXTJS_HOST = os.environ.get("NEXTJS_HOST", "127.0.0.1")
_NEXTJS_PORT = int(os.environ.get("NEXT_PORT", "3000"))
_NEXTJS_BASE = f"http://{_NEXTJS_HOST}:{_NEXTJS_PORT}"

# ── HTTP client for reverse proxy to Next.js ───────────────────
_proxy_client = httpx.AsyncClient(base_url=_NEXTJS_BASE, timeout=30.0)

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
        FileHandler(_log_file, encoding="utf-8"),
        StreamHandler(),
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
    # Ensure required directories exist (important with volumes / fresh containers)
    Path("backend/output").mkdir(parents=True, exist_ok=True)
    Path("backend/logs").mkdir(parents=True, exist_ok=True)

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
    print(f"  Next.js proxy: {_NEXTJS_BASE}")
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

# CORS: allow Railway domains in production, localhost in dev
_cors_regex = os.environ.get(
    "CORS_ORIGIN_REGEX",
    r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=_cors_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Suppress benign SSE disconnect errors (BrokenResourceError from keepalive)
app.add_middleware(_SSEDisconnectMiddleware)

app.include_router(router)

# Serve generated videos as static files
output_dir = Path("backend/output")
output_dir.mkdir(parents=True, exist_ok=True)
if output_dir.exists():
    app.mount("/videos", StaticFiles(directory=str(output_dir)), name="videos")


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


@app.api_route("/{full_path:path}", methods=["GET", "HEAD", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy_to_nextjs(full_path: str, request: Request):
    """Reverse proxy all non-API requests to Next.js server."""
    # Skip API routes and video static files — handled by router/mount above
    if full_path.startswith(("api/", "videos/")):
        from fastapi import HTTPException

        raise HTTPException(status_code=404)

    try:
        # Build the URL for Next.js
        url = f"/{full_path}" if full_path else "/"

        # Forward headers, excluding hop-by-hop headers
        excluded_headers = {
            "host",
            "connection",
            "keep-alive",
            "transfer-encoding",
            "upgrade",
        }
        forward_headers = {
            k: v for k, v in request.headers.items() if k.lower() not in excluded_headers
        }
        # Set host to Next.js
        forward_headers["host"] = f"{_NEXTJS_HOST}:{_NEXTJS_PORT}"

        # Read request body if present
        body = await request.body()

        resp = await _proxy_client.request(
            method=request.method,
            url=url,
            headers=forward_headers,
            content=body or None,
        )

        # Build response with proxied content
        response_headers = {
            k: v for k, v in resp.headers.items() if k.lower() not in ("transfer-encoding", "content-encoding", "content-length")
        }

        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=response_headers,
        )
    except httpx.ConnectError:
        logger.error("Next.js upstream not reachable at %s", _NEXTJS_BASE)
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="Frontend service unavailable")
    except Exception as exc:
        logger.error("Proxy error for /%s: %s", full_path, exc)
        from fastapi import HTTPException

        raise HTTPException(status_code=502, detail="Bad gateway")
