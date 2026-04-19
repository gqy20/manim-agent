"""共享的 pipeline 执行逻辑，消除 routes.py 中线程/inline 双版本重复。"""

import asyncio
import json
import logging
import os
import shutil
import traceback
from pathlib import Path
from typing import Any

from manim_agent.pipeline_events import EventType, PipelineEvent
from .log_config import log_event
from .storage.r2_client import R2Client, is_r2_url, r2_object_key

logger = logging.getLogger(__name__)

_PIPELINE_TIMEOUT_SECONDS = float(
    os.environ.get("MANIM_PIPELINE_TIMEOUT_SECONDS", "3600")
)


class PipelineExecutionError(RuntimeError):
    """Pipeline failure that preserves partial structured output for persistence."""

    def __init__(
        self,
        message: str,
        *,
        pipeline_output: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.pipeline_output = pipeline_output


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _canonicalize_pipeline_artifacts(
    *,
    task_dir: Path,
    output_path: Path,
    final_video: str,
    pipeline_output: dict[str, Any] | None,
    log_callback,
) -> tuple[str, dict[str, Any] | None]:
    """Import successful artifacts back into the task directory when needed."""
    task_dir = task_dir.resolve()
    output_path = output_path.resolve()
    final_video_path = Path(final_video).resolve()
    po_data = dict(pipeline_output) if pipeline_output is not None else None

    canonical_video = final_video_path
    if final_video_path.exists() and not _is_relative_to(final_video_path, task_dir):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(final_video_path, output_path)
        canonical_video = output_path
        log_callback(
            f"[SYS] Imported rendered video into task directory: {canonical_video}"
        )

    if po_data is not None:
        po_data["final_video_output"] = str(canonical_video)
        scene_file = po_data.get("scene_file")
        if scene_file:
            scene_path = Path(scene_file).resolve()
            if scene_path.exists() and not _is_relative_to(scene_path, task_dir):
                imported_scene = task_dir / scene_path.name
                shutil.copy2(scene_path, imported_scene)
                po_data["scene_file"] = str(imported_scene.resolve())
                log_callback(
                    f"[SYS] Imported scene script into task directory: {imported_scene.resolve()}"
                )

    return str(canonical_video), po_data


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


def _write_failure_diagnostics(
    *,
    task_dir: Path,
    dispatcher: Any | None,
    error_message: str,
) -> Path | None:
    """Persist raw pipeline diagnostics for post-mortem analysis."""
    if dispatcher is None:
        return None
    try:
        task_dir.mkdir(parents=True, exist_ok=True)
        diagnostics_path = task_dir / "phase_failure_diagnostics.json"
        payload = {
            "error_message": error_message,
            "phase1": dispatcher.get_phase1_failure_diagnostics(),
            "pipeline_output_snapshot": dispatcher.get_persistable_pipeline_output(),
        }
        diagnostics_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return diagnostics_path
    except Exception:
        logger.exception("Failed to persist pipeline diagnostics for %s", task_dir)
        return None


async def _pipeline_body(
    req: Any,
    task_id: str,
    output_path: str,
    voice_id: str,
    model: str,
    quality: str,
    no_tts: bool,
    bgm_enabled: bool,
    bgm_prompt: str | None,
    bgm_volume: float,
    target_duration_seconds: int,
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
    from manim_agent.pipeline import run_pipeline

    dispatcher_ref: list[Any] = []
    task_dir = Path(cwd).resolve()
    final_output_path = Path(output_path).resolve()
    try:
        log_event(
            logger,
            logging.INFO,
            "pipeline_started",
            task_id=task_id,
            voice_id=voice_id,
            model=model,
            quality=quality,
            no_tts=no_tts,
            bgm_enabled=bgm_enabled,
            target_duration_seconds=target_duration_seconds,
        )
        final_video = await asyncio.wait_for(
            run_pipeline(
                user_text=req.user_text,
                output_path=output_path,
                voice_id=voice_id,
                model=model,
                quality=quality,
                no_tts=no_tts,
                bgm_enabled=bgm_enabled,
                bgm_prompt=bgm_prompt,
                bgm_volume=bgm_volume,
                target_duration_seconds=target_duration_seconds,
                cwd=cwd,
                max_turns=max_turns,
                log_callback=log_callback,
                preset=preset,
                _dispatcher_ref=dispatcher_ref,
                event_callback=event_callback,
            ),
            timeout=_PIPELINE_TIMEOUT_SECONDS,
        )
        # Extract pipeline structured output
        po_data = None
        if dispatcher_ref:
            dispatcher = dispatcher_ref[0]
            po_data = dispatcher.get_persistable_pipeline_output()

        # ── Upload to R2 if configured ──
        final_video, po_data = _canonicalize_pipeline_artifacts(
            task_dir=task_dir,
            output_path=final_output_path,
            final_video=final_video,
            pipeline_output=po_data,
            log_callback=log_callback,
        )
        _video_url: str = final_video  # default: local path
        if r2_client is not None and Path(final_video).exists():
            try:
                obj_key = r2_object_key(task_id)
                log_event(
                    logger,
                    logging.INFO,
                    "r2_upload_started",
                    task_id=task_id,
                    object_key=obj_key,
                )
                _video_url = r2_client.upload_file(final_video, obj_key)
                log_callback(f"[SYS] Video uploaded to R2: {_video_url}")
                log_event(
                    logger,
                    logging.INFO,
                    "r2_upload_completed",
                    task_id=task_id,
                    object_key=obj_key,
                )
            except Exception as exc:
                log_event(
                    logger,
                    logging.WARNING,
                    "r2_upload_failed",
                    task_id=task_id,
                    error_type=type(exc).__name__,
                )
                log_callback("[SYS] R2 upload failed, using local path")

        log_event(
            logger,
            logging.INFO,
            "pipeline_completed",
            task_id=task_id,
            final_video=_video_url,
        )
        return _video_url, po_data

    except asyncio.TimeoutError:
        timeout_min = _PIPELINE_TIMEOUT_SECONDS / 60
        error_message = (
            f"Pipeline exceeded the allowed runtime ({timeout_min:.0f} min) "
            f"and was automatically terminated."
        )
        log_event(
            logger,
            logging.ERROR,
            "pipeline_timeout",
            task_id=task_id,
            timeout_seconds=_PIPELINE_TIMEOUT_SECONDS,
        )
        log_callback(f"[TIMEOUT] {error_message}")
        log_callback(f"[TIMEOUT] Set MANIM_PIPELINE_TIMEOUT_SECONDS to adjust.")
        partial_po_data = None
        if dispatcher_ref:
            dispatcher = dispatcher_ref[0]
            partial_po_data = dispatcher.get_persistable_pipeline_output()
        raise PipelineExecutionError(
            error_message,
            pipeline_output=partial_po_data,
        ) from None

    except Exception as exc:
        error_message = _format_exception_message(exc)
        log_event(
            logger,
            logging.ERROR,
            "pipeline_failed",
            task_id=task_id,
            error_type=type(exc).__name__,
        )
        logger.exception(
            "Task %s failed: %s [type=%s args=%s]",
            task_id,
            error_message,
            type(exc).__name__,
            getattr(exc, "args", None),
        )
        # Push full error chain to log stream
        log_callback(f"[ERR] {error_message}")
        for line in traceback.format_exception(type(exc), exc, exc.__traceback__):
            for ll in line.rstrip().splitlines():
                log_callback(f"[TRACE] {ll}")
        partial_po_data = None
        diagnostics_path = None
        if dispatcher_ref:
            dispatcher = dispatcher_ref[0]
            partial_po_data = dispatcher.get_persistable_pipeline_output()
            diagnostics_path = _write_failure_diagnostics(
                task_dir=task_dir,
                dispatcher=dispatcher,
                error_message=error_message,
            )
        if diagnostics_path is not None:
            log_callback(f"[SYS] Failure diagnostics saved: {diagnostics_path}")
        raise PipelineExecutionError(
            error_message,
            pipeline_output=partial_po_data,
        ) from exc
