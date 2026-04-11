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
from fastapi.responses import FileResponse
from fastapi.sse import EventSourceResponse

from manim_agent.pipeline_events import EventType, PipelineEvent

from .models import (
    SSEEvent,
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


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(req: TaskCreateRequest) -> TaskResponse:
    """Create a task & start the pipeline in background."""
    task = await _store.create(req)
    task_id = task["id"]

    output_dir = Path("backend/output") / task_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(output_dir / "final.mp4")

    # Subscribe SSE queue for this task
    _sse_mgr.subscribe(task_id)

    # Capture the running event loop *before* spawning the thread.
    # Pipeline executes in a dedicated thread with its own asyncio loop so
    # that SDK subprocess creation (create_subprocess_exec) works on
    # Windows / Python 3.13 where ProactorEventLoop forbids subprocess
    # creation inside an already-running loop.
    main_loop = asyncio.get_event_loop()

    def log_callback(line: str) -> None:
        _safe_schedule(main_loop, lambda ln=line: _store.append_log(task_id, ln))
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

        from manim_agent.__main__ import run_pipeline

        log_callback("[SYS] Connecting to Claude Agent SDK...")
        _safe_schedule(
            main_loop,
            lambda: _store.update_status(task_id, TaskStatus.RUNNING),
        )
        # 推送 status 事件让前端 badge 从"等待中"更新为"生成中"
        event_callback(PipelineEvent(event_type=EventType.STATUS, data="running"))

        dispatcher_ref: list[Any] = []
        try:
            final_video = _asyncio.run(
                run_pipeline(
                    user_text=req.user_text,
                    output_path=output_path,
                    voice_id=req.voice_id,
                    model=req.model,
                    quality=req.quality,
                    no_tts=req.no_tts,
                    cwd=str(output_dir),
                    max_turns=50,
                    log_callback=log_callback,
                    preset=req.preset,
                    _dispatcher_ref=dispatcher_ref,
                    event_callback=event_callback,
                )
            )
            # 提取 pipeline 结构化输出
            po_data = None
            if dispatcher_ref:
                dispatcher = dispatcher_ref[0]
                po = dispatcher.get_pipeline_output()
                if po is not None:
                    po_data = po.model_dump()

            _safe_schedule(
                main_loop,
                lambda: _store.update_status(
                    task_id,
                    TaskStatus.COMPLETED,
                    video_path=final_video,
                    pipeline_output=po_data,
                ),
            )
        except Exception as exc:
            error_message = _format_exception_message(exc)
            logger.exception(
                "Task %s failed: %s [type=%s args=%s]",
                task_id,
                error_message,
                type(exc).__name__,
                getattr(exc, "args", None),
            )
            # 将完整错误链写入 log stream（前端可展示）
            log_callback(f"[ERR] {error_message}")
            import traceback as tb

            for line in tb.format_exception(type(exc), exc, exc.__traceback__):
                for ll in line.rstrip().splitlines():
                    log_callback(f"[TRACE] {ll}")
            _safe_schedule(
                main_loop,
                lambda: _store.update_status(task_id, TaskStatus.FAILED, error=error_message),
            )
        finally:
            try:
                main_loop.call_soon_threadsafe(_sse_mgr.done, task_id)
            except RuntimeError:
                pass  # loop closed during shutdown/test teardown

    async def _run_pipeline_inline() -> None:
        """Inline async pipeline — test mode only (no subprocess needed)."""
        from manim_agent.__main__ import run_pipeline

        _sse_mgr.push(task_id, "[SYS] Connecting to Claude Agent SDK...")
        await _store.append_log(task_id, "[SYS] Connecting to Claude Agent SDK...")
        await _store.update_status(task_id, TaskStatus.RUNNING)

        dispatcher_ref: list[Any] = []
        try:
            final_video = await run_pipeline(
                user_text=req.user_text,
                output_path=output_path,
                voice_id=req.voice_id,
                model=req.model,
                quality=req.quality,
                no_tts=req.no_tts,
                cwd=str(output_dir),
                max_turns=50,
                log_callback=log_callback,
                preset=req.preset,
                _dispatcher_ref=dispatcher_ref,
                event_callback=event_callback,
            )
            po_data = None
            if dispatcher_ref:
                dispatcher = dispatcher_ref[0]
                po = dispatcher.get_pipeline_output()
                if po is not None:
                    po_data = po.model_dump()

            await _store.update_status(
                task_id,
                TaskStatus.COMPLETED,
                video_path=final_video,
                pipeline_output=po_data,
            )
        except Exception as exc:
            error_message = _format_exception_message(exc)
            logger.exception(
                "Task %s failed: %s [type=%s args=%s]",
                task_id,
                error_message,
                type(exc).__name__,
                getattr(exc, "args", None),
            )
            log_callback(f"[ERR] {error_message}")
            import traceback as tb

            for line in tb.format_exception(type(exc), exc, exc.__traceback__):
                for ll in line.rstrip().splitlines():
                    log_callback(f"[TRACE] {ll}")
            await _store.update_status(task_id, TaskStatus.FAILED, error=error_message)
        finally:
            _sse_mgr.done(task_id)

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
    """SSE endpoint: stream real-time logs for a running/completed task."""
    task = await _store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Replay existing logs first (supports reconnect)
    for line in task.get("logs", []):
        yield {
            "event": "log",
            "data": SSEEvent(
                event_type="log",
                data=line,
                timestamp=datetime.now(UTC).isoformat(),
            ).model_dump_json(),
        }

    status = task["status"]
    if status in (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value):
        yield {
            "event": "status",
            "data": SSEEvent(
                event_type="status",
                data=status,
                timestamp=datetime.now(UTC).isoformat(),
            ).model_dump_json(),
        }
        return

    # Live streaming from queue
    queue = _sse_mgr.subscribe(task_id)
    try:
        while True:
            item = await queue.get()
            if item is None:  # sentinel
                break
            now = datetime.now(UTC).isoformat()

            # 队列中的 item 已由 SSESubscriptionManager.push() 序列化为 JSON。
            # 直接解析并透传 event_type，避免二次包装导致类型信息丢失。
            if isinstance(item, str) and item.strip().startswith("{"):
                try:
                    parsed = json.loads(item)
                    event_name = parsed.get("event_type", parsed.get("type", "log"))
                    yield {
                        "event": event_name,
                        "data": json.dumps(parsed.get("data", item), ensure_ascii=False),
                    }
                    continue
                except json.JSONDecodeError:
                    pass  # 不是合法 JSON，走兜底

            # 兜底：非 JSON 数据包装为 log 类型
            yield {
                "event": "log",
                "data": SSEEvent(event_type="log", data=item, timestamp=now).model_dump_json(),
            }

        # Send final status after sentinel
        try:
            refreshed = await _store.get(task_id)
            if refreshed:
                yield {
                    "event": "status",
                    "data": SSEEvent(
                        event_type="status",
                        data=refreshed["status"],
                        timestamp=datetime.now(UTC).isoformat(),
                    ).model_dump_json(),
                }
        except Exception:
            # Task may have been cleaned up; ignore and let SSE stream end
            pass
    finally:
        _sse_mgr.unsubscribe(task_id)


@router.get("/{task_id}/video")
async def get_video(task_id: str) -> FileResponse:
    """Serve the generated video file."""
    task = await _store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    video_path = task.get("video_path")
    if not video_path or not Path(video_path).exists():
        raise HTTPException(status_code=404, detail="Video not ready")
    return FileResponse(
        path=video_path,
        media_type="video/mp4",
        filename=f"{task_id}.mp4",
    )
