"""Structured beat and timeline models for audio/video orchestration."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BeatSpec(BaseModel):
    id: str
    title: str
    narration_hint: str | None = None
    narration_text: str | None = None
    target_duration_seconds: float | None = Field(default=None, ge=0)
    actual_audio_duration_seconds: float | None = Field(default=None, ge=0)
    start_seconds: float | None = Field(default=None, ge=0)
    end_seconds: float | None = Field(default=None, ge=0)
    audio_path: str | None = None
    normalized_audio_path: str | None = None
    subtitle_path: str | None = None
    extra_info_path: str | None = None
    tts_mode: str | None = None
    normalization_strategy: str | None = None
    normalized_audio_duration_seconds: float | None = Field(default=None, ge=0)


class AudioSegmentSpec(BaseModel):
    beat_id: str
    audio_path: str
    subtitle_path: str | None = None
    extra_info_path: str | None = None
    duration_seconds: float = Field(ge=0)
    tts_mode: str | None = None


class TimelineSpec(BaseModel):
    beats: list[BeatSpec] = Field(default_factory=list)
    total_duration_seconds: float = Field(default=0, ge=0)


class SegmentRenderSpec(BaseModel):
    beat_id: str
    title: str
    target_duration_seconds: float = Field(ge=0)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    output_path: str
    scene_file: str | None = None
    scene_class: str | None = None


class AudioOrchestrationResult(BaseModel):
    beats: list[BeatSpec] = Field(default_factory=list)
    timeline: TimelineSpec
    timeline_path: str | None = None
    concatenated_audio_path: str | None = None
    concatenated_subtitle_path: str | None = None
    bgm_path: str | None = None
    bgm_duration_ms: int | None = None
    bgm_prompt: str | None = None
