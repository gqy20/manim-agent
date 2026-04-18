"""Phase 1: Scene Planning output schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BuildSpecBeat(BaseModel):
    """A single beat in the approved build specification."""

    id: str = Field(description="Stable beat identifier such as beat_001_intro.")
    title: str = Field(description="Human-readable beat title.")
    visual_goal: str = Field(description="Primary visual outcome for this beat.")
    narration_intent: str = Field(description="Short narration intent aligned to this beat only.")
    target_duration_seconds: float = Field(
        ge=0,
        description="Target beat duration in seconds.",
    )
    required_elements: list[str] = Field(
        default_factory=list,
        description="Visual elements that must be present for this beat.",
    )
    segment_required: bool = Field(
        default=True,
        description="Whether this beat must produce a dedicated rendered segment.",
    )


class BuildSpec(BaseModel):
    """Machine-readable implementation contract emitted by Phase 1."""

    mode: str = Field(description="Short mode label such as proof-walkthrough.")
    learning_goal: str = Field(description="Single-sentence learning goal.")
    audience: str = Field(description="Intended viewer level or audience.")
    target_duration_seconds: int = Field(
        ge=0,
        description="Requested target runtime for the whole video.",
    )
    beats: list[BuildSpecBeat] = Field(
        min_length=1,
        description="Ordered beat list that Phase 2 must execute.",
    )


class Phase1PlanningOutput(BaseModel):
    """Structured output from Phase 1 (scene planning pass)."""

    markdown_plan: str = Field(
        description="Visible Markdown scene plan emitted during the planning pass.",
    )
    build_spec: BuildSpec = Field(
        description="Machine-readable implementation contract for Phase 2.",
    )
