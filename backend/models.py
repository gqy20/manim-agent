"""Pydantic models for the Manim Agent Web API."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

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


class PipelineOutputData(BaseModel):
    """完成任务的 pipeline 结构化输出数据（API 响应用）。"""

    video_output: str | None = None
    scene_file: str | None = None
    scene_class: str | None = None
    duration_seconds: float | None = None
    narration: str | None = None
    source_code: str | None = None


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
