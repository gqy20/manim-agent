"""API route handlers for the manim-agent web backend."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.sse import EventSourceResponse

from .models import (
    SSEEvent,
    TaskCreateRequest,
    TaskListResponse,
    TaskResponse,
    TaskStatus,
)
from .sse_manager import SSESubscriptionManager
from .task_store import TaskStore

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


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(req: TaskCreateRequest) -> TaskResponse:
    """Create a new video generation task and start the pipeline in background."""
    task = await _store.create(req)
    task_id = task["id"]

    output_dir = Path("backend/output") / task_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(output_dir / "final.mp4")

    # Subscribe SSE queue for this task
    queue = _sse_mgr.subscribe(task_id)

    def log_callback(line: str) -> None:
        _sse_mgr.push(task_id, line)
        # Also store in task logs for replay on reconnect
        asyncio.get_event_loop().call_soon_threadsafe(
            lambda: asyncio.create_task(_store.append_log(task_id, line))
        )

    def event_callback(event: Any) -> None:
        """将 Dispatcher 结构化事件推送到 SSE 队列。"""
        _sse_mgr.push(task_id, event)

    async def run_pipeline_background() -> None:
        from manim_agent.__main__ import run_pipeline

        await _store.update_status(task_id, TaskStatus.RUNNING)
        # 用于从 run_pipeline 内部获取 dispatcher 实例
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
            # 提取 pipeline 结构化输出
            po_data = None
            if dispatcher_ref:
                dispatcher = dispatcher_ref[0]
                po = dispatcher.get_pipeline_output()
                if po is not None:
                    po_data = po.model_dump()

            await _store.update_status(
                task_id, TaskStatus.COMPLETED,
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
            # 将完整错误链写入 log stream（前端可展示）
            log_callback(f"[ERR] {error_message}")
            import traceback as tb
            for line in tb.format_exception(type(exc), exc, exc.__traceback__):
                for ll in line.rstrip().splitlines():
                    log_callback(f"[TRACE] {ll}")
            await _store.update_status(
                task_id, TaskStatus.FAILED, error=error_message
            )
        finally:
            _sse_mgr.done(task_id)

    asyncio.create_task(run_pipeline_background())
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
                timestamp=datetime.now(timezone.utc).isoformat(),
            ).model_dump_json(),
        }

    status = task["status"]
    if status in (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value):
        yield {
            "event": "status",
            "data": SSEEvent(
                event_type="status",
                data=status,
                timestamp=datetime.now(timezone.utc).isoformat(),
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
            now = datetime.now(timezone.utc).isoformat()
            yield {
                "event": "log",
                "data": SSEEvent(event_type="log", data=item, timestamp=now)
                .model_dump_json(),
            }

        # Send final status after sentinel
        refreshed = await _store.get(task_id)
        if refreshed:
            yield {
                "event": "status",
                "data": SSEEvent(
                    event_type="status",
                    data=refreshed["status"],
                    timestamp=datetime.now(timezone.utc).isoformat(),
                ).model_dump_json(),
            }
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
