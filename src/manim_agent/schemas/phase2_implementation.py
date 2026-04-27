"""Phase 2: Implementation output schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RenderedSegment(BaseModel):
    """A real beat-level rendered video segment produced during Phase 2."""

    beat_id: str = Field(
        description="Stable beat id from the Phase 1 build_spec.",
        min_length=1,
    )
    title: str = Field(
        description="Human-readable beat title.",
        min_length=1,
    )
    order_index: int = Field(
        ge=0,
        description="Zero-based order in the canonical Phase 1 beat list.",
    )
    video_path: str = Field(
        description="Path to the rendered MP4 for this beat segment.",
        min_length=1,
    )
    duration_seconds: float | None = Field(
        default=None,
        ge=0,
        description="Measured duration of this rendered segment in seconds.",
    )


class Phase2ImplementationOutput(BaseModel):
    """Structured output from Phase 2 (implementation pass)."""

    scene_file: str | None = Field(
        default=None,
        description="Path to the generated Manim scene script.",
    )
    scene_class: str | None = Field(
        default=None,
        description="Primary Manim Scene class rendered for this task.",
    )
    video_output: str | None = Field(
        default=None,
        description="Path to the rendered full-scene MP4 when render_mode is full.",
    )
    implemented_beats: list[str] = Field(
        default_factory=list,
        description="Short list of the beats that were actually implemented in code, in order.",
    )
    build_summary: str | None = Field(
        default=None,
        description="Short summary of what the build phase implemented.",
    )
    narration: str | None = Field(
        default=None,
        description="Natural spoken narration text for the implemented animation.",
    )
    deviations_from_plan: list[str] = Field(
        default_factory=list,
        description="Explicit deviations from the approved build plan/context, if any.",
    )
    render_mode: str | None = Field(
        default=None,
        description="Visual render delivery mode, such as full or segments.",
    )
    segment_render_complete: bool | None = Field(
        default=None,
        description="Whether beat-level segment rendering completed for every planned beat.",
    )
    segment_video_paths: list[str] = Field(
        default_factory=list,
        description="Ordered list of beat-level rendered video segment paths.",
    )
    rendered_segments: list[RenderedSegment] = Field(
        default_factory=list,
        description="Ordered rendered beat segment records, one per implemented beat.",
    )
    source_code: str | None = Field(
        default=None,
        description="Full source code of the generated scene file when captured.",
    )
