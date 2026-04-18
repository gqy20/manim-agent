"""Phase 3: Render Review output schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FrameAnalysis(BaseModel):
    """Per-frame visual analysis result from the render-review pass."""

    frame_path: str = Field(
        ...,
        description="Path to the analyzed frame image file.",
    )
    timestamp_label: str = Field(
        default="",
        description="Beat-aligned label for this frame (e.g. 'opening', 'beat_2', 'ending')",
    )
    visual_assessment: str = Field(
        default="",
        description="Free-text visual description of what appears in this frame.",
    )
    issues_found: list[str] = Field(
        default_factory=list,
        description="Specific visual issues found in this frame.",
    )


class Phase3RenderReviewOutput(BaseModel):
    """Structured review result for post-render quality checks."""

    approved: bool = Field(
        ...,
        description="Whether the rendered video passes the review gate.",
    )
    summary: str = Field(
        ...,
        description="Short overall review summary.",
        min_length=1,
    )
    blocking_issues: list[str] = Field(
        default_factory=list,
        description="Blocking issues that require revision before success.",
    )
    suggested_edits: list[str] = Field(
        default_factory=list,
        description="Concrete revision guidance for the next build pass.",
    )
    frame_analyses: list[FrameAnalysis] = Field(
        default_factory=list,
        description="Per-frame visual analysis details, if vision analysis was performed.",
    )
    vision_analysis_used: bool = Field(
        default=False,
        description="Whether per-frame visual analysis (reading each image) was performed.",
    )
