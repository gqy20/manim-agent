"""Structured planning schema used between Phase 1 and Phase 2."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BuildSpecBeat(BaseModel):
    """A single beat in the approved build specification."""

    id: str = Field(description="Stable beat identifier such as beat_001_intro.")
    title: str = Field(description="Human-readable beat title.")
    visual_goal: str = Field(description="Primary visual outcome for this beat.")
    narration_intent: str = Field(
        description="Short narration intent aligned to this beat only."
    )
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


class ScenePlanOutput(BaseModel):
    """Planning-stage structured output."""

    markdown_plan: str = Field(
        description="Visible Markdown scene plan emitted during the planning pass.",
    )
    build_spec: BuildSpec = Field(
        description="Machine-readable implementation contract for Phase 2.",
    )

    @staticmethod
    def output_format_schema() -> dict[str, Any]:
        """Return the JSON schema expected by ClaudeAgentOptions.output_format."""
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "scene_plan_output",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "markdown_plan": {
                            "type": "string",
                            "description": "Visible Markdown scene plan emitted during the planning pass.",
                        },
                        "build_spec": {
                            "type": "object",
                            "description": "Machine-readable implementation contract for Phase 2.",
                            "properties": {
                                "mode": {
                                    "type": "string",
                                    "description": "Short mode label such as proof-walkthrough.",
                                },
                                "learning_goal": {
                                    "type": "string",
                                    "description": "Single-sentence learning goal.",
                                },
                                "audience": {
                                    "type": "string",
                                    "description": "Intended viewer level or audience.",
                                },
                                "target_duration_seconds": {
                                    "type": "integer",
                                    "description": "Requested target runtime for the whole video.",
                                    "minimum": 0,
                                },
                                "beats": {
                                    "type": "array",
                                    "description": "Ordered beat list that Phase 2 must execute.",
                                    "minItems": 1,
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "id": {
                                                "type": "string",
                                                "description": "Stable beat identifier such as beat_001_intro.",
                                            },
                                            "title": {
                                                "type": "string",
                                                "description": "Human-readable beat title.",
                                            },
                                            "visual_goal": {
                                                "type": "string",
                                                "description": "Primary visual outcome for this beat.",
                                            },
                                            "narration_intent": {
                                                "type": "string",
                                                "description": "Short narration intent aligned to this beat only.",
                                            },
                                            "target_duration_seconds": {
                                                "type": "number",
                                                "description": "Target beat duration in seconds.",
                                                "minimum": 0,
                                            },
                                            "required_elements": {
                                                "type": "array",
                                                "description": "Visual elements that must be present for this beat.",
                                                "items": {"type": "string"},
                                            },
                                            "segment_required": {
                                                "type": "boolean",
                                                "description": "Whether this beat must produce a dedicated rendered segment.",
                                            },
                                        },
                                        "required": [
                                            "id",
                                            "title",
                                            "visual_goal",
                                            "narration_intent",
                                            "target_duration_seconds",
                                            "required_elements",
                                            "segment_required",
                                        ],
                                        "additionalProperties": False,
                                    },
                                },
                            },
                            "required": [
                                "mode",
                                "learning_goal",
                                "audience",
                                "target_duration_seconds",
                                "beats",
                            ],
                            "additionalProperties": False,
                        },
                    },
                    "required": ["markdown_plan", "build_spec"],
                    "additionalProperties": False,
                },
            },
        }
