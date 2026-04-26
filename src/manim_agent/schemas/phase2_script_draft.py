"""Phase 2A: script draft output schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Phase2ScriptDraftOutput(BaseModel):
    """Structured output from Phase 2A before rendering is allowed."""

    scene_file: str = Field(
        description="Path to the generated Manim scene script, normally scene.py.",
    )
    scene_class: str = Field(
        default="GeneratedScene",
        description="Primary Manim Scene class to render later.",
    )
    implemented_beats: list[str] = Field(
        description="Ordered beat titles or ids represented in the script draft.",
        min_length=1,
    )
    build_summary: str = Field(
        description="Short summary of the generated script structure.",
        min_length=1,
    )
    beat_timing_seconds: dict[str, float] = Field(
        description=(
            "Estimated animation duration per implemented beat id, based on explicit "
            "self.play(run_time=...) and self.wait(...) calls in the generated script."
        ),
        min_length=1,
    )
    estimated_duration_seconds: float = Field(
        description="Estimated total animation duration across all beat methods.",
        ge=0,
    )
    deviations_from_plan: list[str] = Field(
        default_factory=list,
        description="Explicit deviations from the approved build_spec, if any.",
    )
    source_code: str = Field(
        description="Full source code of the generated scene file when captured.",
        min_length=1,
    )
