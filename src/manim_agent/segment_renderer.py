"""Helpers for building a future timeline-driven segment render plan."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from pydantic import BaseModel, Field

from .beat_schema import SegmentRenderSpec, TimelineSpec


class SegmentRenderPlan(BaseModel):
    scene_file: str | None = None
    scene_class: str | None = None
    total_duration_seconds: float = Field(default=0, ge=0)
    segments: list[SegmentRenderSpec] = Field(default_factory=list)


def build_segment_render_plan(
    *,
    timeline: TimelineSpec,
    output_dir: str,
    scene_file: str | None,
    scene_class: str | None,
) -> SegmentRenderPlan:
    """Translate a resolved beat timeline into renderable segment specs."""
    root = Path(output_dir) / "segments"
    segments: list[SegmentRenderSpec] = []

    for beat in timeline.beats:
        start = float(beat.start_seconds or 0.0)
        end = float(beat.end_seconds or start)
        duration = max(0.0, end - start)
        if duration <= 0:
            continue
        segments.append(
            SegmentRenderSpec(
                beat_id=beat.id,
                title=beat.title,
                target_duration_seconds=duration,
                start_seconds=start,
                end_seconds=end,
                output_path=str(root / f"{beat.id}.mp4"),
                scene_file=scene_file,
                scene_class=scene_class,
            )
        )

    return SegmentRenderPlan(
        scene_file=scene_file,
        scene_class=scene_class,
        total_duration_seconds=timeline.total_duration_seconds,
        segments=segments,
    )


def build_provisional_segment_render_plan(
    *,
    beat_titles: list[str],
    total_duration_seconds: float,
    output_dir: str,
    scene_file: str | None,
    scene_class: str | None,
) -> SegmentRenderPlan:
    """Build an even-split segment plan when only a full render exists.

    This is a fallback for `render_mode="segments"` runs where the agent
    produced a single full-length video but did not emit per-beat clips.
    """
    normalized_titles = [title.strip() for title in beat_titles if title and title.strip()]
    if not normalized_titles:
        normalized_titles = ["Main narration"]

    total_duration_seconds = max(0.0, float(total_duration_seconds))
    root = Path(output_dir) / "segments"
    count = len(normalized_titles)
    slice_duration = total_duration_seconds / count if count > 0 else 0.0

    segments: list[SegmentRenderSpec] = []
    cursor = 0.0
    for index, title in enumerate(normalized_titles, start=1):
        start = cursor
        end = total_duration_seconds if index == count else cursor + slice_duration
        cursor = end
        segments.append(
            SegmentRenderSpec(
                beat_id=f"beat_{index:03d}",
                title=title,
                target_duration_seconds=max(0.0, end - start),
                start_seconds=start,
                end_seconds=end,
                output_path=str(root / f"beat_{index:03d}.mp4"),
                scene_file=scene_file,
                scene_class=scene_class,
            )
        )

    return SegmentRenderPlan(
        scene_file=scene_file,
        scene_class=scene_class,
        total_duration_seconds=total_duration_seconds,
        segments=segments,
    )


def write_segment_render_plan(plan: SegmentRenderPlan, output_path: str) -> str:
    """Persist a segment render plan as JSON."""
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(plan.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(target)


def read_segment_render_plan(path: str) -> SegmentRenderPlan:
    """Load a persisted segment render plan JSON file."""
    return SegmentRenderPlan.model_validate_json(Path(path).read_text(encoding="utf-8"))


def discover_segment_video_paths(
    *,
    output_dir: str,
    expected_paths: list[str] | None = None,
) -> list[str]:
    """Discover existing beat segment videos under the task output directory.

    If explicit expected paths are provided, preserve that order and only keep
    files that actually exist. Otherwise, scan `<output_dir>/segments/*.mp4`
    and sort by file name for deterministic ordering.
    """
    if expected_paths:
        resolved_expected = [str(Path(path)) for path in expected_paths if path]
        existing = [path for path in resolved_expected if Path(path).exists()]
        if existing:
            return existing

    root = Path(output_dir) / "segments"
    if not root.exists():
        return []

    return [
        str(path)
        for path in sorted(root.glob("*.mp4"))
        if path.is_file() and path.stat().st_size > 0
    ]


async def extract_video_segments(video_path: str, plan: SegmentRenderPlan) -> list[str]:
    """Cut a full rendered video into beat-aligned MP4 segments using FFmpeg."""
    source = Path(video_path)
    if not source.exists():
        raise FileNotFoundError(f"Source video not found: {video_path}")

    outputs: list[str] = []
    for segment in plan.segments:
        target = Path(segment.output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        duration = max(0.0, segment.end_seconds - segment.start_seconds)
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{segment.start_seconds:.3f}",
            "-i",
            str(source),
            "-t",
            f"{duration:.3f}",
            "-c",
            "copy",
            str(target),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(
                f"ffmpeg segment extraction failed for {segment.beat_id}: "
                f"{stderr.decode().strip()}"
            )
        outputs.append(str(target))

    return outputs
