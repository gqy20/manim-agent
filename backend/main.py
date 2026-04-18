"""FastAPI application entry point for manim-agent web backend."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from time import perf_counter
from pathlib import Path

import httpx
from anyio import BrokenResourceError
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

from .log_config import configure_logging, install_request_logging_middleware, log_event
from .routes import _r2_client, clarify_router, init_r2_client, router, set_store
from .task_store import TaskStore

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

_NEXTJS_HOST = os.environ.get("NEXTJS_HOST", "127.0.0.1")
_NEXTJS_PORT = int(os.environ.get("NEXT_PORT", "3000"))
_NEXTJS_BASE = f"http://{_NEXTJS_HOST}:{_NEXTJS_PORT}"

_proxy_client = httpx.AsyncClient(base_url=_NEXTJS_BASE, timeout=30.0)

configure_logging()
logger = logging.getLogger(__name__)


def _is_benign_sse_disconnect(exc: BaseException) -> bool:
    """Return True when the exception only contains SSE disconnect errors."""
    if isinstance(exc, BrokenResourceError):
        return True
    if isinstance(exc, ExceptionGroup):
        return all(_is_benign_sse_disconnect(child) for child in exc.exceptions)
    return False


class _SSEDisconnectMiddleware:
    """Suppress benign SSE disconnect errors when clients close connections."""

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
                log_event(
                    logger,
                    logging.DEBUG,
                    "sse_disconnect_suppressed",
                    route=scope.get("path"),
                    error_type=type(exc).__name__,
                )
                return
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path("backend/output").mkdir(parents=True, exist_ok=True)
    Path("backend/logs").mkdir(parents=True, exist_ok=True)

    store = TaskStore()
    await store.start()
    set_store(store)
    app.state.store = store

    init_r2_client()

    try:
        count = len(await store.list_all(limit=9999))
    except Exception:
        count = 0

    log_event(
        logger,
        logging.INFO,
        "backend_ready",
        task_count=count,
        storage_backend="r2" if _r2_client else "local",
        nextjs_base=_NEXTJS_BASE,
    )

    r2_mode = "R2 (cloud)" if _r2_client else "Local filesystem"
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
    log_event(logger, logging.INFO, "backend_shutdown")
    await store.close()


app = FastAPI(
    title="Manim Agent API",
    description="Web API for AI-driven Manim math animation generation",
    version="0.1.0",
    lifespan=lifespan,
)

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
app.add_middleware(_SSEDisconnectMiddleware)
install_request_logging_middleware(app)

app.include_router(router)
app.include_router(clarify_router)

output_dir = Path("backend/output")
output_dir.mkdir(parents=True, exist_ok=True)
if output_dir.exists():
    app.mount("/videos", StaticFiles(directory=str(output_dir)), name="videos")


@app.get("/api/health")
async def health_check():
    log_event(logger, logging.DEBUG, "health_check_requested", route="/api/health")
    return {"status": "ok"}


@app.api_route(
    "/{full_path:path}",
    methods=["GET", "HEAD", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
)
async def proxy_to_nextjs(full_path: str, request: Request):
    """Reverse proxy all non-API requests to Next.js server."""
    if full_path.startswith(("api/", "videos/")):
        from fastapi import HTTPException

        raise HTTPException(status_code=404)

    route = f"/{full_path}" if full_path else "/"
    started_at = perf_counter()
    try:
        excluded_headers = {
            "host",
            "connection",
            "keep-alive",
            "transfer-encoding",
            "upgrade",
        }
        forward_headers = {
            key: value
            for key, value in request.headers.items()
            if key.lower() not in excluded_headers
        }
        forward_headers["host"] = f"{_NEXTJS_HOST}:{_NEXTJS_PORT}"
        body = await request.body()

        resp = await _proxy_client.request(
            method=request.method,
            url=route,
            headers=forward_headers,
            content=body or None,
        )
        duration_ms = round((perf_counter() - started_at) * 1000, 2)
        log_event(
            logger,
            logging.DEBUG,
            "next_proxy_response",
            route=route,
            method=request.method,
            status_code=resp.status_code,
            duration_ms=duration_ms,
        )

        response_headers = {
            key: value
            for key, value in resp.headers.items()
            if key.lower()
            not in ("transfer-encoding", "content-encoding", "content-length")
        }

        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=response_headers,
        )
    except httpx.ConnectError:
        log_event(
            logger,
            logging.ERROR,
            "next_proxy_connect_error",
            route=route,
            method=request.method,
            upstream=_NEXTJS_BASE,
        )
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="Frontend service unavailable")
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "next_proxy_failed",
            route=route,
            method=request.method,
            error_type=type(exc).__name__,
        )
        from fastapi import HTTPException

        raise HTTPException(status_code=502, detail="Bad gateway")
