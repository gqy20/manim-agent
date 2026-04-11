"""共享的 pipeline 执行逻辑，消除 routes.py 中线程/inline 双版本重复。"""

import asyncio
import logging
import traceback
from pathlib import Path
from typing import Any

from manim_agent.pipeline_events import EventType, PipelineEvent
from .storage.r2_client import R2Client, is_r2_url, r2_object_key

logger = logging.getLogger(__name__)


def _format_exception_message(exc: Exception) -> str:
    """Return a compact, non-empty error summary including chained causes."""
    parts: list[str] = []
    seen: set[int] = set()
    current: BaseException | None = exc

    while current is not None and id(current) not in seen:
        seen.add(id(current))
        raw = str(current).strip() or repr(current)
        label = type(current).__name__
        text = f"{label}: {raw}" if raw else label
        parts.append(text)
        current = current.__cause__ or current.__context__

    return " -> ".join(parts)


def _cleanup_output_dir(output_dir: Path, *, keep_mp4: bool = True) -> None:
    """Remove non-essential files from a task's output directory."""
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
                import shutil

                shutil.rmtree(child, ignore_errors=True)
    except OSError:
        logger.debug("Cleanup skipped for %s", output_dir)


async def _pipeline_body(
    req: Any,
    task_id: str,
    output_path: str,
    voice_id: str,
    model: str,
    quality: str,
    no_tts: bool,
    cwd: str,
    max_turns: int,
    preset: str,
    log_callback,
    event_callback,
    r2_client: R2Client | None,
) -> tuple[str | None, dict | None]:
    """Core pipeline execution body. Returns (video_url_or_None, pipeline_output_or_None).

    Shared by both thread-mode and inline-mode callers.
    Raises on pipeline failure so caller can handle status update.
    """
    from manim_agent.__main__ import run_pipeline

    dispatcher_ref: list[Any] = []
    try:
        final_video = await run_pipeline(
            user_text=req.user_text,
            output_path=output_path,
            voice_id=voice_id,
            model=model,
            quality=quality,
            no_tts=no_tts,
            cwd=cwd,
            max_turns=max_turns,
            log_callback=log_callback,
            preset=preset,
            _dispatcher_ref=dispatcher_ref,
            event_callback=event_callback,
        )
        # Extract pipeline structured output
        po_data = None
        if dispatcher_ref:
            dispatcher = dispatcher_ref[0]
            po = dispatcher.get_pipeline_output()
            if po is not None:
                po_data = po.model_dump()

        # ── Upload to R2 if configured ──
        _video_url: str = final_video  # default: local path
        if r2_client is not None and Path(final_video).exists():
            try:
                obj_key = r2_object_key(task_id)
                _video_url = r2_client.upload_file(final_video, obj_key)
                log_callback(f"[SYS] Video uploaded to R2: {_video_url}")
                try:
                    Path(final_video).unlink()
                except OSError:
                    pass
            except Exception as exc:
                logger.warning("R2 upload failed for task %s, falling back to local: %s", task_id, exc)
                log_callback("[SYS] R2 upload failed, using local path")

        return _video_url, po_data

    except Exception as exc:
        error_message = _format_exception_message(exc)
        logger.exception("Task %s failed: %s [type=%s args=%s]", task_id, error_message, type(exc).__name__, getattr(exc, "args", None))
        # Push full error chain to log stream
        log_callback(f"[ERR] {error_message}")
        for line in traceback.format_exception(type(exc), exc, exc.__traceback__):
            for ll in line.rstrip().splitlines():
                log_callback(f"[TRACE] {ll}")
        raise  # Re-raise so caller can update task status
