"""Phase 5: Mux (audio-video merge) output schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Phase5MuxOutput(BaseModel):
    """Structured output from Phase 5 (final video mux)."""

    final_video_output: str | None = Field(
        default=None,
        description="Path to the final muxed video with narration, if available.",
    )
    duration_seconds: float | None = Field(
        default=None,
        description="Measured duration of the rendered or final video in seconds.",
        ge=0,
    )
    audio_mix_mode: str | None = Field(
        default=None,
        description="Audio mix mode used for the final mux, such as voice_only or voice_with_bgm.",
    )
    bgm_path: str | None = Field(
        default=None,
        description="Path to the generated instrumental background music file, if any.",
    )
    bgm_prompt: str | None = Field(
        default=None,
        description="Prompt used to generate the background music, if any.",
    )
    bgm_duration_ms: int | None = Field(
        default=None,
        description="Measured or provider-reported BGM duration in milliseconds.",
        ge=0,
    )
    bgm_volume: float | None = Field(
        default=None,
        description="BGM mix volume used during final mux, from 0.0 to 1.0.",
        ge=0,
        le=1,
    )
    subtitle_path: str | None = Field(
        default=None,
        description="Path to generated subtitle or caption file, if any.",
    )
