"""API route handlers for the manim-agent web backend."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
try:
    from fastapi.sse import EventSourceResponse
except ImportError:
    from sse_starlette.sse import EventSourceResponse

from .storage.r2_client import R2Client, is_r2_url, r2_object_key
from .pipeline_runner import _pipeline_body

from manim_agent.pipeline_events import EventType, PipelineEvent, StatusPayload

from .models import (
    TaskCreateRequest,
    TaskListResponse,
    TaskResponse,
    TaskStatus,
)
from .sse_manager import SSESubscriptionManager
from .task_store import TaskStore

# In production, pipeline runs in a dedicated thread with its own asyncio
# event loop so SDK subprocess creation works on Windows/Python 3.13.
# Tests set MANIM_AGENT_TEST_MODE=1 to run inline (no subprocess needed).
_USE_PIPELINE_THREAD = os.environ.get("MANIM_AGENT_TEST_MODE") != "1"

router = APIRouter(prefix="/api/tasks", tags=["tasks"])
logger = logging.getLogger(__name__)

_store: TaskStore  # set via set_store()
_sse_mgr: SSESubscriptionManager = SSESubscriptionManager()

_r2_client: R2Client | None = None
_OUTPUT_ROOT = Path("backend/output")
_DEFAULT_KEEP_LOCAL_MP4_TASKS = 20


def _status_event(
    task_status: TaskStatus | str,
    *,
    phase: str | None = None,
    message: str | None = None,
    video_path: str | None = None,
    pipeline_output: dict[str, Any] | None = None,
) -> PipelineEvent:
    """Build a structured status event for SSE consumers."""
    status_value = task_status.value if isinstance(task_status, TaskStatus) else task_status
    return PipelineEvent(
        event_type=EventType.STATUS,
        data=StatusPayload(
            task_status=status_value,
            phase=phase,
            message=message,
            video_path=video_path,
            pipeline_output=pipeline_output,
        ),
    )


def _terminal_status_payload(task: dict[str, Any]) -> dict[str, Any]:
    """Build the canonical terminal status payload from stored task state."""
    status = task["status"]
    return {
        "task_status": status,
        "phase": "done" if status == TaskStatus.COMPLETED.value else None,
        "message": "Pipeline completed" if status == TaskStatus.COMPLETED.value else task.get("error"),
        "video_path": task.get("video_path"),
        "pipeline_output": task.get("pipeline_output"),
    }


def init_r2_client() -> None:
    """Initialize the R2 client from environment variables.

    Called once during app startup. Sets ``_r2_client`` global;
    callers check ``if _r2_client:`` before use.
    """
    global _r2_client
    _r2_client = R2Client.create()
    if _r2_client:
        logger.info(
            "R2 storage enabled (bucket=%s)",
            _r2_client._bucket_display,
        )
    else:
        logger.info("R2 storage not configured — local filesystem only")


def set_store(store: TaskStore) -> None:
    global _store
    _store = store


def get_sse_manager() -> SSESubscriptionManager:
    return _sse_mgr


def _format_exception_message(exc: Exception) -> str:
    """Return a compact, non-empty error summary including chained causes.

    Always includes exception class name so that empty-str exceptions
    (e.g. some SDK internal errors) are still diagnosable.
    """
    parts: list[str] = []
    seen: set[int] = set()
    current: BaseException | None = exc

    while current is not None and id(current) not in seen:
        seen.add(id(current))
        # 始终包含类名，防止空消息导致诊断困难
        raw = str(current).strip() or repr(current)
        label = type(current).__name__
        text = f"{label}: {raw}" if raw else label
        parts.append(text)
        current = current.__cause__ or current.__context__

    return " -> ".join(parts)


def _get_local_mp4_keep_count() -> int:
    """Read the number of local final.mp4 files to keep after upload.

    Default is 20 to support quick spot-checking and comparison work.
    Set to 0 to remove local mp4 files for all tasks in R2 mode.
    """
    raw = os.environ.get("KEEP_LOCAL_MP4_TASKS", str(_DEFAULT_KEEP_LOCAL_MP4_TASKS))
    try:
        value = int(raw)
        return max(0, value)
    except ValueError:
        logger.warning("Invalid KEEP_LOCAL_MP4_TASKS=%r, using default=%d", raw, _DEFAULT_KEEP_LOCAL_MP4_TASKS)
        return _DEFAULT_KEEP_LOCAL_MP4_TASKS


def _latest_output_task_ids(limit: int) -> set[str]:
    """Return task ids of the latest output directories by directory mtime."""
    if limit <= 0 or not _OUTPUT_ROOT.exists():
        return set()

    def _mtime(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0

    entries = [p for p in _OUTPUT_ROOT.iterdir() if p.is_dir()]
    entries.sort(key=_mtime, reverse=True)
    return {p.name for p in entries[:limit]}


def _should_keep_local_video(task_id: str) -> bool:
    """Whether this task should keep local final.mp4 for quick review."""
    keep_count = _get_local_mp4_keep_count()
    if keep_count <= 0:
        return False
    return task_id in _latest_output_task_ids(keep_count)


def _enforce_local_video_retention() -> None:
    """Keep local final.mp4 only for the latest N tasks, remove others."""
    if _r2_client is None:
        return
    keep_count = _get_local_mp4_keep_count()
    if not _OUTPUT_ROOT.exists():
        return

    keep_ids = _latest_output_task_ids(keep_count) if keep_count > 0 else set()
    for task_dir in _OUTPUT_ROOT.iterdir():
        if not task_dir.is_dir() or task_dir.name in keep_ids:
            continue

        final_mp4 = task_dir / "final.mp4"
        if final_mp4.exists():
            try:
                final_mp4.unlink()
            except OSError:
                logger.debug("Failed to prune local final.mp4 for %s", task_dir)


def _safe_schedule(loop: asyncio.AbstractEventLoop, coro_factory) -> None:
    """Thread-safe: schedule an async callable on *loop*.

    Silently drops the callback if the loop is already closed (e.g. during
    test teardown or server shutdown).
    """
    def _schedule() -> None:
        task = asyncio.create_task(coro_factory())

        def _log_task_failure(done_task: asyncio.Task[Any]) -> None:
            try:
                done_task.result()
            except Exception:
                logger.exception("Background task scheduled via _safe_schedule failed")

        task.add_done_callback(_log_task_failure)

    try:
        loop.call_soon_threadsafe(_schedule)
    except RuntimeError:
        # Loop closed — acceptable during shutdown / test cleanup
        pass


def _cleanup_output_dir(output_dir: Path, *, keep_mp4: bool = True) -> None:
    """Remove non-essential files from a task's output directory.

    Keeps ``final.mp4`` and log-like text files when *keep_mp4* is True
    (local serving mode).  When False (R2 active), removes everything since the
    video has already been uploaded to cloud storage.
    """
    if not keep_mp4 and _r2_client is not None:
        # In R2 mode, keep final.mp4 for the most recent tasks only
        # so we can still verify output quickly without filling disk.
        keep_mp4 = _should_keep_local_video(output_dir.name)

    extensions_to_keep = {".log", ".json", ".txt"}
    if keep_mp4:
        extensions_to_keep.add(".mp4")
    try:
        if not output_dir.is_dir():
            return
        for child in output_dir.iterdir():
            if child.is_file() and child.suffix not in extensions_to_keep:
                child.unlink()
            elif child.is_dir():
                # Remove subdirectories entirely (e.g. media/ cache)
                import shutil

                shutil.rmtree(child, ignore_errors=True)
    except OSError:
        logger.debug("Cleanup skipped for %s", output_dir)


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(req: TaskCreateRequest) -> TaskResponse:
    """Create a task & start the pipeline in background."""
    logger.info(
        "POST /api/tasks received: text_len=%d voice=%s model=%s quality=%s preset=%s no_tts=%s target_duration_seconds=%s",
        len(req.user_text),
        req.voice_id,
        req.model,
        req.quality,
        req.preset,
        req.no_tts,
        req.target_duration_seconds,
    )
    task = await _store.create(req)
    task_id = task["id"]
    logger.info("Task created: task_id=%s", task_id)

    output_dir = Path("backend/output") / task_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(output_dir / "final.mp4")

    # 注意：不再需要提前 subscribe() — SSESubscriptionManager v2 自动缓冲事件，
    # 前端连接时通过 subscribe() 回放所有历史事件。
    # Pipeline executes in a dedicated thread with its own asyncio loop so
    # that SDK subprocess creation (create_subprocess_exec) works on
    # Windows / Python 3.13 where ProactorEventLoop forbids subprocess
    # creation inside an already-running loop.
    main_loop = asyncio.get_event_loop()

    def log_callback(line: str) -> None:
        logger.debug("task=%s log_callback line=%r", task_id, line)
        _safe_schedule(
            main_loop, lambda ln=line: _store.append_log(task_id, ln),
        )
        try:
            main_loop.call_soon_threadsafe(_sse_mgr.push, task_id, line)
        except RuntimeError:
            pass  # loop closed during shutdown/test teardown

    # 立即推送启动日志（消除 GAP 1）
    _sse_mgr.push(task_id, f"[SYS] Task {task_id} created")
    await _store.append_log(task_id, f"[SYS] Task {task_id} created")

    def event_callback(event: Any) -> None:
        """将 Dispatcher 结构化事件推送到 SSE 队列。"""
        try:
            logger.debug("task=%s event_callback type=%s", task_id, type(event).__name__)
            main_loop.call_soon_threadsafe(_sse_mgr.push, task_id, event)
        except RuntimeError:
            logger.debug(
                "task=%s event_callback failed to schedule to loop", task_id
            )
            pass  # loop closed during shutdown/test teardown

    def _run_pipeline_thread() -> None:
        """Execute pipeline in a separate thread with its own event loop."""
        logger.info("Task %s pipeline thread started", task_id)
        import asyncio as _asyncio

        log_callback("[SYS] Connecting to Claude Agent SDK...")
        _safe_schedule(
            main_loop,
            lambda: _store.update_status(task_id, TaskStatus.RUNNING),
        )
        event_callback(
            _status_event(
                TaskStatus.RUNNING,
                phase="init",
                message="Pipeline started",
            ),
        )

        try:
            logger.debug("Task %s calling pipeline_body", task_id)
            _video_url, po_data = _asyncio.run(
                _pipeline_body(
                    req=req,
                    task_id=task_id,
                    output_path=output_path,
                    voice_id=req.voice_id,
                    model=req.model,
                    quality=req.quality,
                    no_tts=req.no_tts,
                    target_duration_seconds=req.target_duration_seconds,
                    cwd=str(output_dir),
                    max_turns=50,
                    preset=req.preset,
                    log_callback=log_callback,
                    event_callback=event_callback,
                    r2_client=_r2_client,
                )
            )
            logger.info("Task %s pipeline body returned", task_id)
            _safe_schedule(
                main_loop,
                lambda: _store.update_status(
                    task_id,
                    TaskStatus.COMPLETED,
                    video_path=_video_url,
                    pipeline_output=po_data,
                ),
            )
            event_callback(
                _status_event(
                    TaskStatus.COMPLETED,
                    phase="done",
                    message="Pipeline completed",
                    video_path=_video_url,
                    pipeline_output=po_data,
                ),
            )
        except Exception as exc:
            error_message = _format_exception_message(exc)
            logger.exception("Task %s failed: %s", task_id, error_message)
            _safe_schedule(
                main_loop,
                lambda: _store.update_status(
                    task_id, TaskStatus.FAILED, error=error_message,
                ),
            )
            event_callback(
                _status_event(
                    TaskStatus.FAILED,
                    message=error_message,
                ),
            )
        finally:
            logger.debug("Task %s pipeline thread finalizing", task_id)
            try:
                main_loop.call_soon_threadsafe(_sse_mgr.done, task_id)
            except RuntimeError:
                pass
            _cleanup_output_dir(output_dir, keep_mp4=(_r2_client is None))
            _enforce_local_video_retention()

    async def _run_pipeline_inline() -> None:
        """Inline async pipeline — test mode only."""
        logger.info("Task %s pipeline inline started", task_id)
        msg = "[SYS] Connecting to Claude Agent SDK..."
        _sse_mgr.push(task_id, msg)
        await _store.append_log(task_id, msg)
        await _store.update_status(task_id, TaskStatus.RUNNING)
        event_callback(
            _status_event(
                TaskStatus.RUNNING,
                phase="init",
                message="Pipeline started",
            ),
        )

        try:
            logger.debug("Task %s calling pipeline_body inline", task_id)
            _video_url, po_data = await _pipeline_body(
                req=req,
                task_id=task_id,
                output_path=output_path,
                voice_id=req.voice_id,
                model=req.model,
                quality=req.quality,
                no_tts=req.no_tts,
                target_duration_seconds=req.target_duration_seconds,
                cwd=str(output_dir),
                max_turns=50,
                preset=req.preset,
                log_callback=log_callback,
                event_callback=event_callback,
                r2_client=_r2_client,
            )
            logger.info("Task %s inline pipeline completed video=%s", task_id, _video_url)
            await _store.update_status(
                task_id,
                TaskStatus.COMPLETED,
                video_path=_video_url,
                pipeline_output=po_data,
            )
            event_callback(
                _status_event(
                    TaskStatus.COMPLETED,
                    phase="done",
                    message="Pipeline completed",
                    video_path=_video_url,
                    pipeline_output=po_data,
                ),
            )
        except Exception as exc:
            error_message = _format_exception_message(exc)
            logger.exception("Task %s failed: %s", task_id, error_message)
            await _store.update_status(
                task_id, TaskStatus.FAILED, error=error_message,
            )
            event_callback(
                _status_event(
                    TaskStatus.FAILED,
                    message=error_message,
                ),
            )
        finally:
            logger.debug("Task %s pipeline inline finalizing", task_id)
            _sse_mgr.done(task_id)
            _cleanup_output_dir(output_dir, keep_mp4=(_r2_client is None))
            _enforce_local_video_retention()

    if _USE_PIPELINE_THREAD:
        # Production: dedicated thread with its own asyncio loop.
        # Required for Windows/Python 3.13 where ProactorEventLoop
        # forbids subprocess creation inside a running loop.
        threading.Thread(target=_run_pipeline_thread, daemon=True).start()
    else:
        # Test mode: run inline on the event loop (no subprocess needed).
        asyncio.create_task(_run_pipeline_inline())

    return _store.to_response(task)


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    limit: int = Query(default=50, le=200),
) -> TaskListResponse:
    """List all tasks, most recent first."""
    tasks = await _store.list_all(limit)
    return TaskListResponse(
        tasks=[_store.to_response(t) for t in tasks],
        total=len(tasks),
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str) -> TaskResponse:
    """Get task status and details."""
    task = await _store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return _store.to_response(task)


@router.get("/{task_id}/events", response_class=EventSourceResponse)
async def task_events(task_id: str):
    """SSE endpoint: stream real-time logs for a task with deduplicated replay."""
    logger.debug("SSE events requested for task_id=%r", task_id)
    task = await _store.get(task_id)
    if not task:
        logger.warning("SSE events request for missing task_id=%r", task_id)
        raise HTTPException(status_code=404, detail="Task not found")

    now = datetime.now(UTC).isoformat()
    seen_log_payloads: set[str] = set()
    seen_status_payloads: set[str] = set()

    for line in task.get("logs", []):
        seen_log_payloads.add(str(line))
        yield _make_sse_event("log", {"type": "log", "data": line, "timestamp": now})

    for raw_item in _sse_mgr.get_buffer(task_id):
        try:
            parsed = json.loads(raw_item)
            event_name = parsed.get("type", parsed.get("event_type", "log"))
            if event_name == "log":
                data_val = str(parsed.get("data", ""))
                if data_val in seen_log_payloads:
                    continue
                seen_log_payloads.add(data_val)
            elif event_name == "status":
                payload_key = json.dumps(parsed.get("data", {}), ensure_ascii=False, sort_keys=True)
                if payload_key in seen_status_payloads:
                    continue
                seen_status_payloads.add(payload_key)

            yield _parse_and_yield(parsed, event_name, now)
        except (json.JSONDecodeError, TypeError):
            raw_text = str(raw_item)
            if raw_text in seen_log_payloads:
                continue
            seen_log_payloads.add(raw_text)
            yield _make_sse_event("log", {"type": "log", "data": raw_text, "timestamp": now})

    status = task["status"]
    logger.debug(
        "SSE task=%s initial status=%s history_logs=%d buffered=%d",
        task_id,
        status,
        len(task.get("logs", [])),
        len(_sse_mgr.get_buffer(task_id)),
    )
    if status in (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value):
        payload = _terminal_status_payload(task)
        payload_key = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        if payload_key not in seen_status_payloads:
            yield _make_sse_event(
                "status",
                {
                    "type": "status",
                    "data": payload,
                    "timestamp": now,
                },
            )
        return

    logger.debug("SSE task=%s waiting for queue subscription", task_id)
    queue = _sse_mgr.subscribe(task_id, replay=False)
    try:
        while True:
            item = await queue.get()
            if item is None:
                logger.debug("SSE task=%s queue received done sentinel", task_id)
                break

            event_ts = datetime.now(UTC).isoformat()
            if isinstance(item, str) and item.strip().startswith("{"):
                try:
                    parsed = json.loads(item)
                    event_name = parsed.get("type", parsed.get("event_type", "log"))
                    if event_name == "log":
                        data_val = str(parsed.get("data", ""))
                        if data_val in seen_log_payloads:
                            continue
                        seen_log_payloads.add(data_val)
                    elif event_name == "status":
                        payload_key = json.dumps(parsed.get("data", {}), ensure_ascii=False, sort_keys=True)
                        if payload_key in seen_status_payloads:
                            continue
                        seen_status_payloads.add(payload_key)
                    yield _parse_and_yield(parsed, event_name, event_ts)
                    continue
                except json.JSONDecodeError:
                    pass

            raw_text = str(item)
            if raw_text in seen_log_payloads:
                continue
            seen_log_payloads.add(raw_text)
            yield _make_sse_event("log", {"type": "log", "data": raw_text, "timestamp": event_ts})

        refreshed = await _store.get(task_id)
        if refreshed:
            payload = _terminal_status_payload(refreshed)
            payload_key = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            if payload_key not in seen_status_payloads:
                yield _make_sse_event(
                    "status",
                    {
                        "type": "status",
                        "data": payload,
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                )
    finally:
        logger.debug("SSE task=%s unsubscribe queue", task_id)
        _sse_mgr.unsubscribe(task_id, queue)


def _make_sse_event(event_name: str, payload: dict) -> dict:
    """构建一个 SSE yield 字典。"""
    return {
        "event": event_name,
        "data": json.dumps(payload, ensure_ascii=False),
    }


def _parse_and_yield(
    parsed: dict,
    event_name: str,
    ts: str,
) -> dict:
    """解析已序列化的 SSEEvent 并构造正确的 SSE yield 格式。

    从队列/缓冲区取出的数据格式为：
      {"type": "tool_start", "data": {...}, "timestamp": "..."}
    需要透传给前端，保持 {type, data, timestamp} 结构。
    """
    inner_data = parsed.get("data", parsed)
    return {
        "event": event_name,
        "data": json.dumps(
            {"type": event_name, "data": inner_data, "timestamp": ts},
            ensure_ascii=False,
        ),
    }


@router.get("/{task_id}/video")
async def get_video(task_id: str):
    """Serve the generated video file.

    If the stored video_path is an HTTP(S) URL (R2), redirects the
    client to that URL (zero server bandwidth — CDN delivers directly).
    Otherwise serves from local filesystem (legacy / dev mode).
    """
    task = await _store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    video_path = task.get("video_path")
    if not video_path:
        raise HTTPException(status_code=404, detail="Video not ready")

    # R2 mode: redirect to public URL (CDN handles delivery)
    if is_r2_url(video_path):
        return RedirectResponse(url=video_path, status_code=302)

    # Local mode: serve from disk
    if not Path(video_path).exists():
        raise HTTPException(status_code=404, detail="Video file not found on disk")
    return FileResponse(
        path=video_path,
        media_type="video/mp4",
        filename=f"{task_id}.mp4",
    )


# ── 前端日志接收端点 ──────────────────────────────────────────
_FRONTEND_LOG_DIR = Path("backend/logs")


@router.post("/frontend-logs", status_code=204)
async def receive_frontend_logs(request: Request):
    """接收前端日志并按会话 ID 写入 backend/logs/frontend-{sessionId}.log (NDJSON)."""
    body = await request.json()
    entries = body if isinstance(body, list) else [body]

    _FRONTEND_LOG_DIR.mkdir(parents=True, exist_ok=True)

    # 按 sessionId 分组写入不同文件
    by_session: dict[str, list[dict]] = {}
    for entry in entries:
        sid = entry.get("sessionId", "unknown")
        by_session.setdefault(sid, []).append(entry)

    for sid, group in by_session.items():
        log_file = _FRONTEND_LOG_DIR / f"frontend-{sid}.log"
        with log_file.open("a", encoding="utf-8") as f:
            for entry in group:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    logger.debug("Received %d frontend log entries across %d sessions",
                 len(entries), len(by_session))
    return Response(status_code=204)
