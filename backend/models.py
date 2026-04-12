"""Pydantic models for the Manim Agent Web API."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskCreateRequest(BaseModel):
    user_text: str = Field(..., min_length=1, max_length=5000)
    voice_id: str = "female-tianmei"
    model: str = "speech-2.8-hd"
    quality: str = "high"  # high | medium | low
    preset: str = "default"  # default | educational | presentation | proof | concept
    no_tts: bool = False
    target_duration_seconds: Literal[30, 60, 180, 300] = 60


class PipelineOutputData(BaseModel):
    """完成任务的 pipeline 结构化输出数据（API 响应用）。"""

    video_output: str | None = None
    final_video_output: str | None = None
    scene_file: str | None = None
    scene_class: str | None = None
    duration_seconds: float | None = None
    narration: str | None = None
    implemented_beats: list[str] = Field(default_factory=list)
    build_summary: str | None = None
    deviations_from_plan: list[str] = Field(default_factory=list)
    beat_to_narration_map: list[str] = Field(default_factory=list)
    narration_coverage_complete: bool | None = None
    estimated_narration_duration_seconds: float | None = None
    source_code: str | None = None
    audio_path: str | None = None
    subtitle_path: str | None = None
    extra_info_path: str | None = None
    tts_mode: str | None = None
    tts_duration_ms: int | None = None
    tts_word_count: int | None = None
    tts_usage_characters: int | None = None
    target_duration_seconds: int | None = None
    plan_text: str | None = None
    review_summary: str | None = None
    review_approved: bool | None = None
    review_blocking_issues: list[str] = Field(default_factory=list)
    review_suggested_edits: list[str] = Field(default_factory=list)
    review_frame_paths: list[str] = Field(default_factory=list)


class TaskResponse(BaseModel):
    id: str
    user_text: str
    status: TaskStatus
    created_at: str  # ISO 8601
    completed_at: str | None = None
    video_path: str | None = None
    error: str | None = None
    options: dict[str, Any]
    pipeline_output: PipelineOutputData | None = None


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]
    total: int


class SSEEvent(BaseModel):
    event_type: str = Field(
        ...,
        alias="type",
        description=(
            "SSE event name: log, status, error, "
            "tool_start, tool_result, thinking, progress"
        ),
    )
    data: str | dict[str, Any] = Field(
        ...,
        description="事件载荷：纯文本日志或结构化字典",
    )
    timestamp: str = Field(..., description="ISO 8601 时间戳")

    model_config = {"populate_by_name": True}
