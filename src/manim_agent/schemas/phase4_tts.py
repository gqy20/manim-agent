"""Phase 4: TTS output schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Phase4TTSOutput(BaseModel):
    """Structured output from Phase 4 (Text-to-Speech generation)."""

    audio_path: str | None = Field(
        default=None,
        description="Path to the generated narration audio file.",
    )
    narration: str | None = Field(
        default=None,
        description="Narration text used for TTS.",
    )
    estimated_narration_duration_seconds: float | None = Field(
        default=None,
        description="Estimated spoken duration of the narration in seconds.",
        ge=0,
    )
    tts_mode: str | None = Field(
        default=None,
        description="TTS transport mode used for this task, such as sync or async.",
    )
    tts_duration_ms: int | None = Field(
        default=None,
        description="Provider-reported audio duration in milliseconds.",
        ge=0,
    )
    tts_word_count: int | None = Field(
        default=None,
        description="Provider-reported word or character count for the narration.",
        ge=0,
    )
    tts_usage_characters: int | None = Field(
        default=None,
        description="Provider-reported billable character count.",
        ge=0,
    )
    extra_info_path: str | None = Field(
        default=None,
        description="Path to extra TTS metadata emitted by the provider.",
    )
