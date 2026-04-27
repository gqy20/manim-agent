"""Phase 3.5: Narration generation output schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BeatNarration(BaseModel):
    """Beat-level spoken narration aligned to one visual segment."""

    beat_id: str = Field(
        description="Stable beat id from the Phase 1 build_spec.",
        min_length=1,
    )
    title: str = Field(
        description="Human-readable beat title.",
        min_length=1,
    )
    text: str = Field(
        description="Spoken Simplified Chinese narration for this beat only.",
        min_length=1,
    )
    target_duration_seconds: float = Field(
        ge=0,
        description="Visual duration this narration should fit.",
    )


class Phase3_5NarrationOutput(BaseModel):
    """Structured output from Phase 3.5 narration generation pass."""

    narration: str = Field(
        description="Generated spoken Chinese narration text covering all implemented beats.",
        min_length=1,
    )
    beat_coverage: list[str] = Field(
        description="Ordered list of beats covered by this narration, "
        "corresponding to implemented_beats from Phase 2B.",
        min_length=1,
    )
    beat_narrations: list[BeatNarration] = Field(
        default_factory=list,
        description="Ordered beat-level narration snippets aligned to visual beat durations.",
    )
    char_count: int = Field(
        description="Total character count of the narration text.",
        ge=1,
    )
    generation_method: str = Field(
        description="How this narration was produced: 'llm' for AI-generated, "
        "'template' for fallback template-based assembly.",
    )
