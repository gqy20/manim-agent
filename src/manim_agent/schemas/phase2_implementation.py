"""Phase 2: Implementation output schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
    implemented_beats: list[str] = Field(
        default_factory=list,
        description="Short list of the beats that were actually implemented in code, in order.",
    )
    build_summary: str | None = Field(
        default=None,
        description="Short summary of what the build phase implemented.",
    )
    deviations_from_plan: list[str] = Field(
        default_factory=list,
        description="Explicit deviations from the visible plan, if any.",
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
    source_code: str | None = Field(
        default=None,
        description="Full source code of the generated scene file when captured.",
    )
