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
    STOPPED = "stopped"


class TaskCreateRequest(BaseModel):
    user_text: str = Field(..., min_length=1, max_length=5000)
    voice_id: str = "female-tianmei"
    model: str = "speech-2.8-hd"
    quality: str = "high"  # high | medium | low
    preset: str = "default"  # default | educational | presentation | proof | concept
    no_tts: bool = False
    bgm_enabled: bool = False
    bgm_prompt: str | None = None
    bgm_volume: float = Field(default=0.12, ge=0.0, le=1.0)
    target_duration_seconds: Literal[30, 60, 180, 300] = 60


class ContentClarifyRequest(BaseModel):
    user_text: str = Field(..., min_length=1, max_length=3000)


class ContentClarifyData(BaseModel):
    topic_interpretation: str = Field(..., min_length=1)
    core_question: str = Field(..., min_length=1)
    prerequisite_concepts: list[str] = Field(default_factory=list)
    explanation_path: list[str] = Field(default_factory=list)
    scope_boundaries: list[str] = Field(default_factory=list)
    optional_branches: list[str] = Field(default_factory=list)
    animation_focus: list[str] = Field(default_factory=list)
    ambiguity_notes: list[str] = Field(default_factory=list)
    clarified_brief_cn: str = Field(..., min_length=1)
    recommended_request_cn: str = Field(..., min_length=1)


class ContentClarifyResponse(BaseModel):
    original_user_text: str
    clarification: ContentClarifyData


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
    render_mode: str | None = None
    segment_render_complete: bool | None = None
    beats: list[dict[str, Any]] = Field(default_factory=list)
    audio_segments: list[dict[str, Any]] = Field(default_factory=list)
    timeline_path: str | None = None
    timeline_total_duration_seconds: float | None = None
    segment_render_plan_path: str | None = None
    segment_video_paths: list[str] = Field(default_factory=list)
    audio_concat_path: str | None = None
    source_code: str | None = None
    audio_path: str | None = None
    bgm_path: str | None = None
    bgm_prompt: str | None = None
    bgm_duration_ms: int | None = None
    bgm_volume: float | None = None
    audio_mix_mode: str | None = None
    subtitle_path: str | None = None
    extra_info_path: str | None = None
    tts_mode: str | None = None
    tts_duration_ms: int | None = None
    tts_word_count: int | None = None
    tts_usage_characters: int | None = None
    run_turns: int | None = None
    run_tool_use_count: int | None = None
    run_tool_stats: dict[str, int] = Field(default_factory=dict)
    run_duration_ms: int | None = None
    run_cost_usd: float | None = None
    target_duration_seconds: int | None = None
    plan_text: str | None = None
    mode: str | None = None
    learning_goal: str | None = None
    audience: str | None = None
    phase1_planning: dict[str, Any] | None = None
    phase2_implementation: dict[str, Any] | None = None
    phase3_render_review: dict[str, Any] | None = None
    phase4_tts: dict[str, Any] | None = None
    phase5_mux: dict[str, Any] | None = None
    review_summary: str | None = None
    review_approved: bool | None = None
    review_blocking_issues: list[str] = Field(default_factory=list)
    review_suggested_edits: list[str] = Field(default_factory=list)
    review_frame_paths: list[str] = Field(default_factory=list)
    review_frame_analyses: list[dict] = Field(default_factory=list)
    review_vision_analysis_used: bool | None = None
    intro_requested: bool | None = None
    outro_requested: bool | None = None
    intro_spec: dict[str, Any] | None = None
    outro_spec: dict[str, Any] | None = None
    intro_video_path: str | None = None
    outro_video_path: str | None = None
    intro_outro_backend: str | None = None


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
