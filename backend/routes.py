"""API route handlers for the manim-agent web backend."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
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

from manim_agent.event_store import EventStore
from manim_agent.pipeline_events import EventType, PipelineEvent, StatusPayload

from .content_clarifier import ContentClarifyError, clarify_content
from .log_config import bind_log_context, get_log_context, log_event, set_log_context
from .models import (
    ContentClarifyRequest,
    ContentClarifyResponse,
    DebugIssueCreateRequest,
    DebugIssueListResponse,
    DebugIssueResponse,
    DebugIssueUpdateRequest,
    DebugPromptArtifactResponse,
    DebugPromptIndexResponse,
    TaskCreateRequest,
    TaskListResponse,
    TaskResponse,
    TaskStatus,
)
from .paths import BACKEND_LOG_ROOT, BACKEND_OUTPUT_ROOT
from .pipeline_runner import PipelineExecutionError, _pipeline_body
from .sse_manager import SSESubscriptionManager
from .storage.r2_client import R2Client, is_r2_url, r2_object_key
from .task_runtime import (
    TaskRuntime,
    TaskTerminationRequested,
    get_task_runtime,
    register_task_runtime,
    unregister_task_runtime,
)
from .task_store import TaskStore

# In production, pipeline runs in a dedicated thread with its own asyncio
# event loop so SDK subprocess creation works on Windows/Python 3.13.
# Tests set MANIM_AGENT_TEST_MODE=1 to run inline (no subprocess needed).
_USE_PIPELINE_THREAD = os.environ.get("MANIM_AGENT_TEST_MODE") != "1"

router = APIRouter(prefix="/api/tasks", tags=["tasks"])
clarify_router = APIRouter(prefix="/api", tags=["clarify"])
logger = logging.getLogger(__name__)

_store: TaskStore  # set via set_store()

_r2_client: R2Client | None = None
_OUTPUT_ROOT = BACKEND_OUTPUT_ROOT
_EVENT_STORE_DIR = _OUTPUT_ROOT / "events"
_event_store: EventStore = EventStore(store_dir=str(_EVENT_STORE_DIR))
_sse_mgr: SSESubscriptionManager = SSESubscriptionManager(event_store=_event_store)
_DEFAULT_KEEP_LOCAL_MP4_TASKS = 20
_TERMINAL_TASK_STATUSES = {
    TaskStatus.COMPLETED.value,
    TaskStatus.FAILED.value,
    TaskStatus.STOPPED.value,
}


def _prompt_debug_enabled() -> bool:
    return os.environ.get("ENABLE_PROMPT_DEBUG", "").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _require_prompt_debug_enabled() -> None:
    if not _prompt_debug_enabled():
        raise HTTPException(status_code=404, detail="Prompt debug is disabled")


def _task_debug_dir(task_id: str) -> Path:
    return (_OUTPUT_ROOT / task_id / "debug").resolve()


def _read_debug_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise HTTPException(status_code=404, detail="Debug artifact not found") from None
    if not isinstance(data, dict):
        raise HTTPException(status_code=404, detail="Debug artifact is invalid")
    return data


@clarify_router.post("/clarify-content", response_model=ContentClarifyResponse)
async def clarify_content_route(req: ContentClarifyRequest) -> ContentClarifyResponse:
    """Clarify a short user topic into a richer content brief."""
    log_event(
        logger,
        logging.INFO,
        "clarify_content_requested",
        route="/api/clarify-content",
        text_len=len(req.user_text),
    )
    try:
        clarification = await clarify_content(req.user_text)
    except ContentClarifyError as exc:
        log_event(
            logger,
            logging.ERROR,
            "clarify_content_failed",
            route="/api/clarify-content",
            error_type=type(exc).__name__,
        )
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    log_event(
        logger,
        logging.INFO,
        "clarify_content_succeeded",
        route="/api/clarify-content",
        core_question=clarification.core_question,
    )

    return ContentClarifyResponse(
        original_user_text=req.user_text,
        clarification=clarification,
    )


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
    if status == TaskStatus.COMPLETED.value:
        message = "Pipeline completed"
        phase = "done"
    elif status == TaskStatus.STOPPED.value:
        message = task.get("error") or "Task terminated by user."
        phase = None
    else:
        message = task.get("error")
        phase = None
    return {
        "task_status": status,
        "phase": phase,
        "message": message,
        "video_path": task.get("video_path"),
        "pipeline_output": task.get("pipeline_output"),
    }


def _task_update_kwargs(
    *,
    video_path: str | None = None,
    error: str | None = None,
    pipeline_output: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build task update kwargs without clearing existing pipeline_output by accident."""
    kwargs: dict[str, Any] = {}
    if video_path is not None:
        kwargs["video_path"] = video_path
    if error is not None:
        kwargs["error"] = error
    if pipeline_output is not None:
        kwargs["pipeline_output"] = pipeline_output
    return kwargs


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
        logger.warning(
            "Invalid KEEP_LOCAL_MP4_TASKS=%r, using default=%d",
            raw,
            _DEFAULT_KEEP_LOCAL_MP4_TASKS,
        )
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


def _delete_task_output_dir(task_id: str) -> None:
    task_dir = _OUTPUT_ROOT / task_id
    if not task_dir.exists():
        return
    try:
        shutil.rmtree(task_dir, ignore_errors=False)
    except OSError:
        logger.debug("Failed to delete output directory for %s", task_id)


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

    extensions_to_keep = {".log", ".json", ".py", ".txt"}
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


async def _mark_task_stopped(
    task_id: str,
    *,
    message: str = "Task terminated by user.",
) -> None:
    await _store.update_status(
        task_id,
        TaskStatus.STOPPED,
        error=message,
    )
    log_event(
        logger,
        logging.INFO,
        "task_terminated",
        task_id=task_id,
        task_status=TaskStatus.STOPPED.value,
    )
    _sse_mgr.push(
        task_id,
        _status_event(
            TaskStatus.STOPPED,
            message=message,
        ),
    )
    _sse_mgr.done(task_id)


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(req: TaskCreateRequest) -> TaskResponse:
    """Create a task & start the pipeline in background."""
    log_event(
        logger,
        logging.INFO,
        "task_create_requested",
        route="/api/tasks",
        text_len=len(req.user_text),
        voice_id=req.voice_id,
        model=req.model,
        quality=req.quality,
        preset=req.preset,
        no_tts=req.no_tts,
        bgm_enabled=req.bgm_enabled,
        bgm_volume=req.bgm_volume,
        target_duration_seconds=req.target_duration_seconds,
    )
    task = await _store.create(req)
    task_id = task["id"]
    bind_log_context(task_id=task_id)
    execution_log_context = get_log_context()
    log_event(
        logger,
        logging.INFO,
        "task_created",
        route="/api/tasks",
        task_id=task_id,
        task_status=task.get("status"),
    )

    output_dir = _OUTPUT_ROOT / task_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(output_dir / "final.mp4")
    runtime = register_task_runtime(
        task_id,
        TaskRuntime(task_id=task_id, mode="thread" if _USE_PIPELINE_THREAD else "inline"),
    )

    # 注意：不再需要提前 subscribe() — SSESubscriptionManager v2 自动缓冲事件，
    # 前端连接时通过 subscribe() 回放所有历史事件。
    # Pipeline executes in a dedicated thread with its own asyncio loop so
    # that SDK subprocess creation (create_subprocess_exec) works on
    # Windows / Python 3.13 where ProactorEventLoop forbids subprocess
    # creation inside an already-running loop.
    main_loop = asyncio.get_event_loop()

    def log_callback(line: str) -> None:
        if runtime.cancel_requested:
            return
        logger.debug("task=%s log_callback line=%r", task_id, line)
        _safe_schedule(
            main_loop,
            lambda ln=line: _store.append_log(task_id, ln),
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
        if runtime.cancel_requested:
            return
        try:
            logger.debug("task=%s event_callback type=%s", task_id, type(event).__name__)
            if isinstance(event, PipelineEvent) and event.event_type == EventType.STATUS:
                data = event.data
                if isinstance(data, StatusPayload) and data.pipeline_output is not None:
                    status = TaskStatus(data.task_status)
                    pipeline_output = data.pipeline_output
                    _safe_schedule(
                        main_loop,
                        lambda st=status, po=pipeline_output: _store.update_status(
                            task_id,
                            st,
                            pipeline_output=po,
                        ),
                    )
            main_loop.call_soon_threadsafe(_sse_mgr.push, task_id, event)
        except RuntimeError:
            logger.debug("task=%s event_callback failed to schedule to loop", task_id)
            pass  # loop closed during shutdown/test teardown

    def _run_pipeline_thread() -> None:
        """Execute pipeline in a separate thread with its own event loop."""
        previous_log_context = get_log_context()
        set_log_context(execution_log_context)
        runtime.set_thread_id(threading.get_ident())
        log_event(logger, logging.INFO, "pipeline_thread_started", task_id=task_id)
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
            if runtime.cancel_requested:
                raise TaskTerminationRequested
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
                    bgm_enabled=req.bgm_enabled,
                    bgm_prompt=req.bgm_prompt,
                    bgm_volume=req.bgm_volume,
                    target_duration_seconds=req.target_duration_seconds,
                    cwd=str(output_dir),
                    max_turns=200,
                    preset=req.preset,
                    log_callback=log_callback,
                    event_callback=event_callback,
                    r2_client=_r2_client,
                )
            )
            logger.info("Task %s pipeline body returned", task_id)
            if runtime.cancel_requested:
                raise TaskTerminationRequested
            _safe_schedule(
                main_loop,
                lambda: _store.update_status(
                    task_id,
                    TaskStatus.COMPLETED,
                    **_task_update_kwargs(video_path=_video_url, pipeline_output=po_data),
                ),
            )
            log_event(
                logger,
                logging.INFO,
                "task_completed",
                task_id=task_id,
                task_status=TaskStatus.COMPLETED.value,
                video_path=_video_url,
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
        except TaskTerminationRequested:
            _safe_schedule(main_loop, lambda: _mark_task_stopped(task_id))
        except Exception as exc:
            error_message = _format_exception_message(exc)
            logger.exception("Task %s failed: %s", task_id, error_message)
            po_data = exc.pipeline_output if isinstance(exc, PipelineExecutionError) else None
            _safe_schedule(
                main_loop,
                lambda: _store.update_status(
                    task_id,
                    TaskStatus.FAILED,
                    **_task_update_kwargs(error=error_message, pipeline_output=po_data),
                ),
            )
            log_event(
                logger,
                logging.ERROR,
                "task_failed",
                task_id=task_id,
                task_status=TaskStatus.FAILED.value,
                error_type=type(exc).__name__,
            )
            event_callback(
                _status_event(
                    TaskStatus.FAILED,
                    message=error_message,
                    pipeline_output=po_data,
                ),
            )
        finally:
            logger.debug("Task %s pipeline thread finalizing", task_id)
            if not runtime.cancel_requested:
                try:
                    main_loop.call_soon_threadsafe(_sse_mgr.done, task_id)
                except RuntimeError:
                    pass
            _cleanup_output_dir(output_dir, keep_mp4=(_r2_client is None))
            _enforce_local_video_retention()
            unregister_task_runtime(task_id)
            set_log_context(previous_log_context)

    async def _run_pipeline_inline() -> None:
        """Inline async pipeline – test mode only."""
        previous_log_context = get_log_context()
        set_log_context(execution_log_context)
        log_event(logger, logging.INFO, "pipeline_inline_started", task_id=task_id)
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
            if runtime.cancel_requested:
                raise TaskTerminationRequested
            logger.debug("Task %s calling pipeline_body inline", task_id)
            _video_url, po_data = await _pipeline_body(
                req=req,
                task_id=task_id,
                output_path=output_path,
                voice_id=req.voice_id,
                model=req.model,
                quality=req.quality,
                no_tts=req.no_tts,
                bgm_enabled=req.bgm_enabled,
                bgm_prompt=req.bgm_prompt,
                bgm_volume=req.bgm_volume,
                target_duration_seconds=req.target_duration_seconds,
                cwd=str(output_dir),
                max_turns=80,
                preset=req.preset,
                log_callback=log_callback,
                event_callback=event_callback,
                r2_client=_r2_client,
            )
            logger.info("Task %s inline pipeline completed video=%s", task_id, _video_url)
            if runtime.cancel_requested:
                raise TaskTerminationRequested
            completed_kwargs = _task_update_kwargs(video_path=_video_url, pipeline_output=po_data)
            await _store.update_status(task_id, TaskStatus.COMPLETED, **completed_kwargs)
            log_event(
                logger,
                logging.INFO,
                "task_completed",
                task_id=task_id,
                task_status=TaskStatus.COMPLETED.value,
                video_path=_video_url,
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
        except (TaskTerminationRequested, asyncio.CancelledError):
            await _mark_task_stopped(task_id)
        except Exception as exc:
            error_message = _format_exception_message(exc)
            logger.exception("Task %s failed: %s", task_id, error_message)
            po_data = exc.pipeline_output if isinstance(exc, PipelineExecutionError) else None
            failed_kwargs = _task_update_kwargs(error=error_message, pipeline_output=po_data)
            await _store.update_status(task_id, TaskStatus.FAILED, **failed_kwargs)
            log_event(
                logger,
                logging.ERROR,
                "task_failed",
                task_id=task_id,
                task_status=TaskStatus.FAILED.value,
                error_type=type(exc).__name__,
            )
            event_callback(
                _status_event(
                    TaskStatus.FAILED,
                    message=error_message,
                    pipeline_output=po_data,
                ),
            )
        finally:
            logger.debug("Task %s pipeline inline finalizing", task_id)
            if not runtime.cancel_requested:
                _sse_mgr.done(task_id)
            _cleanup_output_dir(output_dir, keep_mp4=(_r2_client is None))
            _enforce_local_video_retention()
            unregister_task_runtime(task_id)
            set_log_context(previous_log_context)

    if _USE_PIPELINE_THREAD:
        # Production: dedicated thread with its own asyncio loop.
        # Required for Windows/Python 3.13 where ProactorEventLoop
        # forbids subprocess creation inside a running loop.
        threading.Thread(target=_run_pipeline_thread, daemon=True).start()
    else:
        # Test mode: run inline on the event loop (no subprocess needed).
        inline_task = asyncio.create_task(_run_pipeline_inline())
        runtime.set_async_task(inline_task)

    return _store.to_response(task)


@router.post("/{task_id}/terminate", response_model=TaskResponse)
async def terminate_task(task_id: str) -> TaskResponse:
    """Request termination for a running or pending task."""
    task = await _store.get(task_id)
    if not task:
        log_event(
            logger,
            logging.INFO,
            "task_not_found",
            route="/api/tasks/{task_id}/terminate",
            task_id=task_id,
        )
        raise HTTPException(status_code=404, detail="Task not found")

    status = task.get("status")
    if status in _TERMINAL_TASK_STATUSES:
        log_event(
            logger,
            logging.INFO,
            "task_terminate_noop",
            route="/api/tasks/{task_id}/terminate",
            task_id=task_id,
            task_status=status,
        )
        return _store.to_response(task)

    runtime = get_task_runtime(task_id)
    if runtime is not None:
        runtime.request_termination()

    await _mark_task_stopped(task_id)
    refreshed = await _store.get(task_id)
    if refreshed is None:
        refreshed = {
            **task,
            "status": TaskStatus.STOPPED.value,
            "error": "Task terminated by user.",
        }
    return _store.to_response(refreshed)


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: str) -> Response:
    """Delete a terminal task and its persisted artifacts."""
    task = await _store.get(task_id)
    if not task:
        log_event(
            logger,
            logging.INFO,
            "task_not_found",
            route="/api/tasks/{task_id}",
            task_id=task_id,
        )
        raise HTTPException(status_code=404, detail="Task not found")

    status = task.get("status")
    if status not in _TERMINAL_TASK_STATUSES:
        log_event(
            logger,
            logging.WARNING,
            "task_delete_rejected_non_terminal",
            route="/api/tasks/{task_id}",
            task_id=task_id,
            task_status=status,
        )
        raise HTTPException(status_code=409, detail="Task must be terminated before deletion")

    if _r2_client is not None and task.get("video_path") and is_r2_url(task.get("video_path")):
        _r2_client.delete_object(r2_object_key(task_id))

    _delete_task_output_dir(task_id)
    unregister_task_runtime(task_id)
    _sse_mgr.cleanup(task_id)
    await _store.delete(task_id)

    log_event(
        logger,
        logging.INFO,
        "task_deleted",
        route="/api/tasks/{task_id}",
        task_id=task_id,
        task_status=status,
    )
    return Response(status_code=204)


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    limit: int = Query(default=50, le=200),
) -> TaskListResponse:
    """List all tasks, most recent first."""
    log_event(
        logger,
        logging.INFO,
        "task_list_requested",
        route="/api/tasks",
        limit=limit,
    )
    tasks = await _store.list_all(limit)
    log_event(
        logger,
        logging.INFO,
        "task_list_succeeded",
        route="/api/tasks",
        count=len(tasks),
    )
    return TaskListResponse(
        tasks=[_store.to_response(t) for t in tasks],
        total=len(tasks),
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str) -> TaskResponse:
    """Get task status and details."""
    task = await _store.get(task_id)
    if not task:
        log_event(
            logger,
            logging.INFO,
            "task_not_found",
            route="/api/tasks/{task_id}",
            task_id=task_id,
        )
        raise HTTPException(status_code=404, detail="Task not found")
    log_event(
        logger,
        logging.INFO,
        "task_fetched",
        route="/api/tasks/{task_id}",
        task_id=task_id,
        task_status=task.get("status"),
    )
    return _store.to_response(task)


@router.get("/{task_id}/debug/prompts", response_model=DebugPromptIndexResponse)
async def get_task_debug_prompts(task_id: str) -> DebugPromptIndexResponse:
    _require_prompt_debug_enabled()
    if not await _store.get(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    index_path = _task_debug_dir(task_id) / "prompt_index.json"
    data = _read_debug_json(index_path)
    return DebugPromptIndexResponse(**data)


@router.get(
    "/{task_id}/debug/prompts/{phase_id}",
    response_model=DebugPromptArtifactResponse,
)
async def get_task_debug_prompt_artifact(
    task_id: str,
    phase_id: str,
) -> DebugPromptArtifactResponse:
    _require_prompt_debug_enabled()
    if not await _store.get(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    safe_phase_id = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in phase_id)
    artifact_path = _task_debug_dir(task_id) / f"{safe_phase_id}.prompt.json"
    data = _read_debug_json(artifact_path)
    return DebugPromptArtifactResponse(**data)


@router.get("/{task_id}/debug/issues", response_model=DebugIssueListResponse)
async def list_task_debug_issues(task_id: str) -> DebugIssueListResponse:
    _require_prompt_debug_enabled()
    if not await _store.get(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    issues = await _store.list_debug_issues(task_id)
    return DebugIssueListResponse(
        issues=[DebugIssueResponse(**issue) for issue in issues],
        total=len(issues),
    )


@router.post("/{task_id}/debug/issues", response_model=DebugIssueResponse, status_code=201)
async def create_task_debug_issue(
    task_id: str,
    req: DebugIssueCreateRequest,
) -> DebugIssueResponse:
    _require_prompt_debug_enabled()
    if not await _store.get(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    issue = await _store.create_debug_issue(task_id, req.model_dump())
    return DebugIssueResponse(**issue)


@router.patch("/debug/issues/{issue_id}", response_model=DebugIssueResponse)
async def update_debug_issue(
    issue_id: str,
    req: DebugIssueUpdateRequest,
) -> DebugIssueResponse:
    _require_prompt_debug_enabled()
    issue = await _store.update_debug_issue(
        issue_id,
        req.model_dump(exclude_unset=True),
    )
    if issue is None:
        raise HTTPException(status_code=404, detail="Debug issue not found")
    return DebugIssueResponse(**issue)


@router.delete("/debug/issues/{issue_id}", status_code=204)
async def delete_debug_issue(issue_id: str) -> Response:
    _require_prompt_debug_enabled()
    deleted = await _store.delete_debug_issue(issue_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Debug issue not found")
    return Response(status_code=204)


@router.get("/{task_id}/events", response_class=EventSourceResponse)
async def task_events(task_id: str):
    """SSE endpoint: stream real-time logs for a task with deduplicated replay."""
    log_event(
        logger,
        logging.DEBUG,
        "sse_events_requested",
        route="/api/tasks/{task_id}/events",
        task_id=task_id,
    )
    task = await _store.get(task_id)
    if not task:
        log_event(
            logger,
            logging.INFO,
            "sse_task_not_found",
            route="/api/tasks/{task_id}/events",
            task_id=task_id,
        )
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
    log_event(
        logger,
        logging.DEBUG,
        "sse_stream_replaying",
        route="/api/tasks/{task_id}/events",
        task_id=task_id,
        task_status=status,
        history_logs=len(task.get("logs", [])),
        buffered_count=len(_sse_mgr.get_buffer(task_id)),
    )
    if status in _TERMINAL_TASK_STATUSES:
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

    log_event(
        logger,
        logging.DEBUG,
        "sse_queue_subscribed",
        route="/api/tasks/{task_id}/events",
        task_id=task_id,
    )
    queue = _sse_mgr.subscribe(task_id, replay=False)
    try:
        while True:
            item = await queue.get()
            if item is None:
                log_event(
                    logger,
                    logging.DEBUG,
                    "sse_queue_closed",
                    route="/api/tasks/{task_id}/events",
                    task_id=task_id,
                )
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
                        payload_key = json.dumps(
                            parsed.get("data", {}),
                            ensure_ascii=False,
                            sort_keys=True,
                        )
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
        log_event(
            logger,
            logging.DEBUG,
            "sse_queue_unsubscribed",
            route="/api/tasks/{task_id}/events",
            task_id=task_id,
        )
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
        log_event(
            logger,
            logging.INFO,
            "task_not_found",
            route="/api/tasks/{task_id}/video",
            task_id=task_id,
        )
        raise HTTPException(status_code=404, detail="Task not found")
    video_path = task.get("video_path")
    if not video_path:
        log_event(
            logger,
            logging.INFO,
            "task_video_not_ready",
            route="/api/tasks/{task_id}/video",
            task_id=task_id,
            task_status=task.get("status"),
        )
        raise HTTPException(status_code=404, detail="Video not ready")

    # R2 mode: redirect to public URL (CDN handles delivery)
    if is_r2_url(video_path):
        log_event(
            logger,
            logging.INFO,
            "task_video_redirected",
            route="/api/tasks/{task_id}/video",
            task_id=task_id,
        )
        return RedirectResponse(url=video_path, status_code=302)

    # Local mode: serve from disk
    if not Path(video_path).exists():
        log_event(
            logger,
            logging.WARNING,
            "task_video_missing_on_disk",
            route="/api/tasks/{task_id}/video",
            task_id=task_id,
            video_path=video_path,
        )
        raise HTTPException(status_code=404, detail="Video file not found on disk")
    log_event(
        logger,
        logging.INFO,
        "task_video_served",
        route="/api/tasks/{task_id}/video",
        task_id=task_id,
        video_path=video_path,
    )
    return FileResponse(
        path=video_path,
        media_type="video/mp4",
        filename=f"{task_id}.mp4",
    )


# ── 前端日志接收端点 ──────────────────────────────────────────
_FRONTEND_LOG_DIR = BACKEND_LOG_ROOT


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

    log_event(
        logger,
        logging.INFO,
        "frontend_logs_received",
        route="/api/tasks/frontend-logs",
        entries_count=len(entries),
        session_count=len(by_session),
        session_ids_sample=sorted(by_session)[:3],
    )
    return Response(status_code=204)
