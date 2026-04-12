"""Structured output schema for rendered-video review passes."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FrameAnalysis(BaseModel):
    """Per-frame visual analysis result from the render-review pass."""

    frame_path: str = Field(
        ...,
        description="Path to the analyzed frame image file.",
    )
    timestamp_label: str = Field(
        default="",
        description="Beat-aligned label for this frame (e.g. 'opening', 'beat_2__Core formula', 'ending').",
    )
    visual_assessment: str = Field(
        default="",
        description="Free-text visual description of what appears in this frame.",
    )
    issues_found: list[str] = Field(
        default_factory=list,
        description="Specific visual issues found in this frame.",
    )


class RenderReviewOutput(BaseModel):
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
        description="Whether per-frame visual analysis (reading each image) was performed during this review.",
    )

    @staticmethod
    def output_format_schema() -> dict[str, Any]:
        """Generate the JSON schema required by ClaudeAgentOptions.output_format."""
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "render_review_output",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "approved": {
                            "type": "boolean",
                            "description": "Whether the rendered video passes review.",
                        },
                        "summary": {
                            "type": "string",
                            "description": "Short overall review summary.",
                            "minLength": 1,
                        },
                        "blocking_issues": {
                            "type": "array",
                            "description": "Blocking issues that require revision.",
                            "items": {"type": "string"},
                        },
                        "suggested_edits": {
                            "type": "array",
                            "description": "Concrete revision suggestions.",
                            "items": {"type": "string"},
                        },
                        "frame_analyses": {
                            "type": "array",
                            "description": "Per-frame visual analysis details.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "frame_path": {
                                        "type": "string",
                                        "description": "Path to the analyzed frame image file.",
                                    },
                                    "timestamp_label": {
                                        "type": "string",
                                        "description": "Beat-aligned label for this frame.",
                                    },
                                    "visual_assessment": {
                                        "type": "string",
                                        "description": "Visual description of what appears in this frame.",
                                    },
                                    "issues_found": {
                                        "type": "array",
                                        "description": "Specific visual issues in this frame.",
                                        "items": {"type": "string"},
                                    },
                                },
                                "required": ["frame_path"],
                                "additionalProperties": False,
                            },
                        },
                        "vision_analysis_used": {
                            "type": "boolean",
                            "description": "Whether per-frame visual analysis was performed.",
                        },
                    },
                    "required": [
                        "approved",
                        "summary",
                        "blocking_issues",
                        "suggested_edits",
                    ],
                    "additionalProperties": False,
                },
            },
        }
