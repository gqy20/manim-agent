"""Logging helpers for the backend.

This module keeps the current project on stdlib logging while introducing a
consistent event-style API and request/task context propagation.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from logging import FileHandler, Formatter, LogRecord, StreamHandler
from pathlib import Path
from typing import Any

from fastapi import Request

_LOG_CONTEXT: ContextVar[dict[str, Any]] = ContextVar("backend_log_context", default={})

_STANDARD_RECORD_FIELDS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}


def bind_log_context(**fields: Any) -> None:
    """Merge persistent context fields for subsequent log events."""
    current = dict(_LOG_CONTEXT.get())
    current.update({key: value for key, value in fields.items() if value is not None})
    _LOG_CONTEXT.set(current)


def set_log_context(fields: dict[str, Any] | None) -> None:
    """Replace the full logging context."""
    _LOG_CONTEXT.set({key: value for key, value in (fields or {}).items() if value is not None})


def clear_log_context(*keys: str) -> None:
    """Clear specific context keys or reset the whole context."""
    if not keys:
        _LOG_CONTEXT.set({})
        return
    current = dict(_LOG_CONTEXT.get())
    for key in keys:
        current.pop(key, None)
    _LOG_CONTEXT.set(current)


def get_log_context() -> dict[str, Any]:
    """Return the currently bound logging context."""
    return dict(_LOG_CONTEXT.get())


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    /,
    **fields: Any,
) -> None:
    """Emit a structured event using stdlib logging extras."""
    extra = get_log_context()
    extra.update({key: value for key, value in fields.items() if value is not None})
    extra["event"] = event
    logger.log(level, event, extra=extra)


class _JsonFormatter(Formatter):
    def format(self, record: LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": getattr(record, "event", record.getMessage()),
        }
        for key, value in record.__dict__.items():
            if key in _STANDARD_RECORD_FIELDS or key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class _PlainTextFormatter(Formatter):
    def format(self, record: LogRecord) -> str:
        extras: list[str] = []
        for key, value in record.__dict__.items():
            if key in _STANDARD_RECORD_FIELDS or key == "event" or key.startswith("_"):
                continue
            extras.append(f"{key}={value}")
        prefix = (
            f"{datetime.now(UTC).isoformat()} "
            f"[{record.levelname}] {record.name}: {getattr(record, 'event', record.getMessage())}"
        )
        return f"{prefix} {' '.join(extras)}".rstrip()


def configure_logging(
    *,
    level: str | None = None,
    json_logs: bool | None = None,
    log_dir: str | Path | None = None,
) -> None:
    """Configure root logging for backend processes."""
    resolved_level = (level or os.environ.get("LOG_LEVEL", "INFO")).upper()
    use_json = json_logs if json_logs is not None else os.environ.get("LOG_JSON") == "1"
    target_dir = Path(log_dir or "backend/logs")
    target_dir.mkdir(parents=True, exist_ok=True)
    log_file = target_dir / f"manim-agent-{os.getpid()}.log"

    formatter: Formatter = _JsonFormatter() if use_json else _PlainTextFormatter()

    root = logging.getLogger()
    root.setLevel(getattr(logging, resolved_level, logging.INFO))
    root.handlers.clear()

    file_handler = FileHandler(log_file, encoding="utf-8")
    stream_handler = StreamHandler()
    for handler in (file_handler, stream_handler):
        handler.setFormatter(formatter)
        root.addHandler(handler)

    # Third-party client libraries can be extremely chatty on successful
    # requests; keep them visible only when they emit warnings/errors.
    for logger_name in ("httpx", "httpcore"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def install_request_logging_middleware(app: Any) -> None:
    """Attach request lifecycle logging to a FastAPI/Starlette app."""
    logger = logging.getLogger("backend.http")

    @app.middleware("http")
    async def _request_logging_middleware(request: Request, call_next):
        request_id = request.headers.get("x-request-id", uuid.uuid4().hex[:12])
        bind_log_context(request_id=request_id)
        started_at = time.perf_counter()
        log_event(
            logger,
            logging.INFO,
            "request_started",
            method=request.method,
            route=request.url.path,
        )
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            log_event(
                logger,
                logging.ERROR,
                "request_failed",
                method=request.method,
                route=request.url.path,
                duration_ms=duration_ms,
                error_type=type(exc).__name__,
            )
            clear_log_context("request_id")
            raise

        response.headers["x-request-id"] = request_id
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        log_event(
            logger,
            logging.INFO,
            "request_finished",
            method=request.method,
            route=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        clear_log_context("request_id")
        return response
