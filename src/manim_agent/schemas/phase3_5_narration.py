"""Phase 3.5: Narration generation output schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
    char_count: int = Field(
        description="Total character count of the narration text.",
        ge=1,
    )
    generation_method: str = Field(
        description="How this narration was produced: 'llm' for AI-generated, "
        "'template' for fallback template-based assembly.",
    )
