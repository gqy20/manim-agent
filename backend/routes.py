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

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.sse import EventSourceResponse

from .storage.r2_client import R2Client, is_r2_url, r2_object_key
from .pipeline_runner import _pipeline_body

from manim_agent.pipeline_events import EventType, PipelineEvent

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


def _safe_schedule(loop: asyncio.AbstractEventLoop, coro_factory) -> None:
    """Thread-safe: schedule an async callable on *loop*.

    Silently drops the callback if the loop is already closed (e.g. during
    test teardown or server shutdown).
    """
    try:
        loop.call_soon_threadsafe(lambda: asyncio.create_task(coro_factory()))
    except RuntimeError:
        # Loop closed — acceptable during shutdown / test cleanup
        pass


def _cleanup_output_dir(output_dir: Path, *, keep_mp4: bool = True) -> None:
    """Remove non-essential files from a task's output directory.

    Keeps ``final.mp4`` and log-like text files when *keep_mp4* is True
    (local serving mode).  When False (R2 active), removes everything since the
    video has already been uploaded to cloud storage.
    """
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
    task = await _store.create(req)
    task_id = task["id"]

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
            main_loop.call_soon_threadsafe(_sse_mgr.push, task_id, event)
        except RuntimeError:
            pass  # loop closed during shutdown/test teardown

    def _run_pipeline_thread() -> None:
        """Execute pipeline in a separate thread with its own event loop."""
        import asyncio as _asyncio

        log_callback("[SYS] Connecting to Claude Agent SDK...")
        _safe_schedule(
            main_loop,
            lambda: _store.update_status(task_id, TaskStatus.RUNNING),
        )
        event_callback(
            PipelineEvent(event_type=EventType.STATUS, data="running"),
        )

        try:
            _video_url, po_data = _asyncio.run(
                _pipeline_body(
                    req=req,
                    task_id=task_id,
                    output_path=output_path,
                    voice_id=req.voice_id,
                    model=req.model,
                    quality=req.quality,
                    no_tts=req.no_tts,
                    cwd=str(output_dir),
                    max_turns=50,
                    preset=req.preset,
                    log_callback=log_callback,
                    event_callback=event_callback,
                    r2_client=_r2_client,
                )
            )
            _safe_schedule(
                main_loop,
                lambda: _store.update_status(
                    task_id,
                    TaskStatus.COMPLETED,
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
        finally:
            try:
                main_loop.call_soon_threadsafe(_sse_mgr.done, task_id)
            except RuntimeError:
                pass
            _cleanup_output_dir(output_dir, keep_mp4=(_r2_client is None))

    async def _run_pipeline_inline() -> None:
        """Inline async pipeline — test mode only."""
        msg = "[SYS] Connecting to Claude Agent SDK..."
        _sse_mgr.push(task_id, msg)
        await _store.append_log(task_id, msg)
        await _store.update_status(task_id, TaskStatus.RUNNING)

        try:
            _video_url, po_data = await _pipeline_body(
                req=req,
                task_id=task_id,
                output_path=output_path,
                voice_id=req.voice_id,
                model=req.model,
                quality=req.quality,
                no_tts=req.no_tts,
                cwd=str(output_dir),
                max_turns=50,
                preset=req.preset,
                log_callback=log_callback,
                event_callback=event_callback,
                r2_client=_r2_client,
            )
            await _store.update_status(
                task_id,
                TaskStatus.COMPLETED,
                video_path=_video_url,
                pipeline_output=po_data,
            )
        except Exception as exc:
            error_message = _format_exception_message(exc)
            logger.exception("Task %s failed: %s", task_id, error_message)
            await _store.update_status(
                task_id, TaskStatus.FAILED, error=error_message,
            )
        finally:
            _sse_mgr.done(task_id)
            _cleanup_output_dir(output_dir, keep_mp4=(_r2_client is None))

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
    """SSE endpoint: stream real-time logs for a running/completed task.

    数据流：
    1. 回放 text logs（来自 TaskStore，纯文本日志）
    2. 回放 structured events buffer（来自 SSESubscriptionManager，
       包含 thinking / tool_start / tool_result / progress 等结构化事件）
    3. 终态任务（completed/failed）发送 status 后结束
    4. 运行中任务订阅 live queue 接收实时事件
    """
    task = await _store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    _now = datetime.now(UTC).isoformat()

    # ── Phase 1: 回放文本日志（TaskStore 持久化） ────────────
    for line in task.get("logs", []):
        yield _make_sse_event("log", {"type": "log", "data": line, "timestamp": _now})

    # ── Phase 2: 回放结构化事件缓冲区 ───────────────────────
    # SSEManager v2 缓冲了所有 push() 的事件，subscribe() 时自动回放
    buffered = _sse_mgr.get_buffer(task_id)
    already_seen: set[int] = set()  # 避免与 text logs 重复（log 类型事件）
    for raw_item in buffered:
        try:
            parsed = json.loads(raw_item)
            event_name = parsed.get("type", parsed.get("event_type", "log"))
            # 跳过已在 Phase 1 回放过的纯 log 事件（通过 data 内容去重）
            if event_name == "log":
                data_val = parsed.get("data", "")
                data_hash = hash(str(data_val))
                if data_hash in already_seen:
                    continue
                already_seen.add(data_hash)

            yield _parse_and_yield(parsed, event_name, _now)
        except (json.JSONDecodeError, TypeError):
            # 非法 JSON 走兜底
            yield _make_sse_event("log", {"type": "log", "data": raw_item, "timestamp": _now})

    # ── Phase 3: 终态任务直接返回 ───────────────────────────
    status = task["status"]
    if status in (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value):
        yield _make_sse_event("status", {"type": "status", "data": status, "timestamp": _now})
        return

    # ── Phase 4: 实时流式推送 ───────────────────────────────
    queue = _sse_mgr.subscribe(task_id)
    try:
        while True:
            item = await queue.get()
            if item is None:  # sentinel — pipeline 结束
                break
            now = datetime.now(UTC).isoformat()

            if isinstance(item, str) and item.strip().startswith("{"):
                try:
                    parsed = json.loads(item)
                    event_name = parsed.get("type", parsed.get("event_type", "log"))
                    yield _parse_and_yield(parsed, event_name, now)
                    continue
                except json.JSONDecodeError:
                    pass

            # 兜底：非 JSON 数据
            yield _make_sse_event("log", {"type": "log", "data": item, "timestamp": now})

        # Pipeline 结束后查询最终状态
        try:
            refreshed = await _store.get(task_id)
            if refreshed:
                _final_ts = datetime.now(UTC).isoformat()
                yield _make_sse_event(
                    "status",
                    {"type": "status", "data": refreshed["status"], "timestamp": _final_ts},
                )
        except Exception:
            pass
    finally:
        _sse_mgr.unsubscribe(task_id, queue)


# ── SSE 事件构建辅助函数 ────────────────────────────────────


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
