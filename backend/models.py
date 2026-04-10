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


class TaskResponse(BaseModel):
    id: str
    user_text: str
    status: TaskStatus
    created_at: str  # ISO 8601
    completed_at: str | None = None
    video_path: str | None = None
    error: str | None = None
    options: dict[str, Any]


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]
    total: int


class SSEEvent(BaseModel):
    event_type: str = Field(..., alias="type")  # "log" | "status" | "error"
    data: str
    timestamp: str  # ISO 8601

    model_config = {"populate_by_name": True}
