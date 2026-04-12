"""Structured output schema for rendered-video review passes."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


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
