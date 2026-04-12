"""Structured output schema for the main Manim generation pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PipelineOutput(BaseModel):
    """Structured pipeline output shared between Claude, backend, and UI."""

    video_output: str = Field(
        ...,
        description="Path to the rendered scene video before final mux.",
        min_length=1,
    )
    final_video_output: str | None = Field(
        default=None,
        description="Path to the final muxed video with narration, if available.",
    )
    scene_file: str | None = Field(
        default=None,
        description="Path to the generated Manim scene script.",
    )
    scene_class: str | None = Field(
        default=None,
        description="Primary Manim Scene class rendered for this task.",
    )
    duration_seconds: float | None = Field(
        default=None,
        description="Measured duration of the rendered or final video in seconds.",
        ge=0,
    )
    narration: str | None = Field(
        default=None,
        description="Narration text used for TTS.",
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
    beat_to_narration_map: list[str] = Field(
        default_factory=list,
        description="One short narration mapping line per beat, in visual order.",
    )
    narration_coverage_complete: bool | None = Field(
        default=None,
        description="Whether the narration covers the full beat sequence from opening to ending.",
    )
    estimated_narration_duration_seconds: float | None = Field(
        default=None,
        description="Estimated spoken duration of the narration in seconds.",
        ge=0,
    )
    source_code: str | None = Field(
        default=None,
        description="Full source code of the generated scene file when captured.",
    )
    audio_path: str | None = Field(
        default=None,
        description="Path to the generated narration audio file.",
    )
    bgm_path: str | None = Field(
        default=None,
        description="Path to the generated instrumental background music file, if any.",
    )
    bgm_prompt: str | None = Field(
        default=None,
        description="Prompt used to generate the background music, if any.",
    )
    bgm_duration_ms: int | None = Field(
        default=None,
        description="Measured or provider-reported BGM duration in milliseconds.",
        ge=0,
    )
    bgm_volume: float | None = Field(
        default=None,
        description="BGM mix volume used during final mux, from 0.0 to 1.0.",
        ge=0,
        le=1,
    )
    audio_mix_mode: str | None = Field(
        default=None,
        description="Audio mix mode used for the final mux, such as voice_only or voice_with_bgm.",
    )
    subtitle_path: str | None = Field(
        default=None,
        description="Path to generated subtitle or caption file, if any.",
    )
    extra_info_path: str | None = Field(
        default=None,
        description="Path to extra TTS metadata emitted by the provider.",
    )
    tts_mode: str | None = Field(
        default=None,
        description="TTS transport mode used for this task, such as sync or async.",
    )
    tts_duration_ms: int | None = Field(
        default=None,
        description="Provider-reported audio duration in milliseconds.",
        ge=0,
    )
    tts_word_count: int | None = Field(
        default=None,
        description="Provider-reported word or character count for the narration.",
        ge=0,
    )
    tts_usage_characters: int | None = Field(
        default=None,
        description="Provider-reported billable character count.",
        ge=0,
    )
    run_turns: int | None = Field(
        default=None,
        description="Number of Claude turns used for this run.",
        ge=0,
    )
    run_tool_use_count: int | None = Field(
        default=None,
        description="Total number of tool calls used during the run.",
        ge=0,
    )
    run_tool_stats: dict[str, int] = Field(
        default_factory=dict,
        description="Per-tool usage counts for the run.",
    )
    run_duration_ms: int | None = Field(
        default=None,
        description="Total SDK-reported runtime in milliseconds for the run.",
        ge=0,
    )
    run_cost_usd: float | None = Field(
        default=None,
        description="Total SDK-reported run cost in USD.",
        ge=0,
    )
    target_duration_seconds: int | None = Field(
        default=None,
        description="Requested target runtime for the final video in seconds.",
        ge=0,
    )
    plan_text: str | None = Field(
        default=None,
        description="Visible scene plan emitted before implementation.",
    )
    review_summary: str | None = Field(
        default=None,
        description="Summary of the post-render review pass.",
    )
    review_approved: bool | None = Field(
        default=None,
        description="Whether the render review approved the video.",
    )
    review_blocking_issues: list[str] = Field(
        default_factory=list,
        description="Blocking issues found during render review.",
    )
    review_suggested_edits: list[str] = Field(
        default_factory=list,
        description="Suggested edits from the render review step.",
    )
    review_frame_paths: list[str] = Field(
        default_factory=list,
        description="Sampled frame image paths inspected during render review.",
    )

    @staticmethod
    def output_format_schema() -> dict[str, Any]:
        """Return the JSON schema expected by ClaudeAgentOptions.output_format."""
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "pipeline_output",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "video_output": {
                            "type": "string",
                            "description": "Path to the rendered scene video before final mux.",
                            "minLength": 1,
                        },
                        "final_video_output": {
                            "type": ["string", "null"],
                            "description": "Path to the final muxed video with narration, if available.",
                        },
                        "scene_file": {
                            "type": ["string", "null"],
                            "description": "Path to the generated Manim scene script.",
                        },
                        "scene_class": {
                            "type": ["string", "null"],
                            "description": "Primary Manim Scene class rendered for this task.",
                        },
                        "duration_seconds": {
                            "type": ["number", "null"],
                            "description": "Measured duration of the rendered or final video in seconds.",
                            "minimum": 0,
                        },
                        "narration": {
                            "type": ["string", "null"],
                            "description": "Narration text used for TTS.",
                        },
                        "implemented_beats": {
                            "type": "array",
                            "description": "Short list of the beats that were actually implemented in code, in order.",
                            "items": {"type": "string"},
                        },
                        "build_summary": {
                            "type": ["string", "null"],
                            "description": "Short summary of what the build phase implemented.",
                        },
                        "deviations_from_plan": {
                            "type": "array",
                            "description": "Explicit deviations from the visible plan, if any.",
                            "items": {"type": "string"},
                        },
                        "beat_to_narration_map": {
                            "type": "array",
                            "description": "One short narration mapping line per beat, in visual order.",
                            "items": {"type": "string"},
                        },
                        "narration_coverage_complete": {
                            "type": ["boolean", "null"],
                            "description": "Whether the narration covers the full beat sequence from opening to ending.",
                        },
                        "estimated_narration_duration_seconds": {
                            "type": ["number", "null"],
                            "description": "Estimated spoken duration of the narration in seconds.",
                            "minimum": 0,
                        },
                        "source_code": {
                            "type": ["string", "null"],
                            "description": "Full source code of the generated scene file when captured.",
                        },
                        "audio_path": {
                            "type": ["string", "null"],
                            "description": "Path to the generated narration audio file.",
                        },
                        "bgm_path": {
                            "type": ["string", "null"],
                            "description": "Path to the generated instrumental background music file, if any.",
                        },
                        "bgm_prompt": {
                            "type": ["string", "null"],
                            "description": "Prompt used to generate the background music, if any.",
                        },
                        "bgm_duration_ms": {
                            "type": ["integer", "null"],
                            "description": "Measured or provider-reported BGM duration in milliseconds.",
                            "minimum": 0,
                        },
                        "bgm_volume": {
                            "type": ["number", "null"],
                            "description": "BGM mix volume used during final mux, from 0.0 to 1.0.",
                            "minimum": 0,
                            "maximum": 1,
                        },
                        "audio_mix_mode": {
                            "type": ["string", "null"],
                            "description": "Audio mix mode used for the final mux, such as voice_only or voice_with_bgm.",
                        },
                        "subtitle_path": {
                            "type": ["string", "null"],
                            "description": "Path to generated subtitle or caption file, if any.",
                        },
                        "extra_info_path": {
                            "type": ["string", "null"],
                            "description": "Path to extra TTS metadata emitted by the provider.",
                        },
                        "tts_mode": {
                            "type": ["string", "null"],
                            "description": "TTS transport mode used for this task, such as sync or async.",
                        },
                        "tts_duration_ms": {
                            "type": ["integer", "null"],
                            "description": "Provider-reported audio duration in milliseconds.",
                            "minimum": 0,
                        },
                        "tts_word_count": {
                            "type": ["integer", "null"],
                            "description": "Provider-reported word or character count for the narration.",
                            "minimum": 0,
                        },
                        "tts_usage_characters": {
                            "type": ["integer", "null"],
                            "description": "Provider-reported billable character count.",
                            "minimum": 0,
                        },
                        "run_turns": {
                            "type": ["integer", "null"],
                            "description": "Number of Claude turns used for this run.",
                            "minimum": 0,
                        },
                        "run_tool_use_count": {
                            "type": ["integer", "null"],
                            "description": "Total number of tool calls used during the run.",
                            "minimum": 0,
                        },
                        "run_tool_stats": {
                            "type": "object",
                            "description": "Per-tool usage counts for the run.",
                            "additionalProperties": {"type": "integer", "minimum": 0},
                        },
                        "run_duration_ms": {
                            "type": ["integer", "null"],
                            "description": "Total SDK-reported runtime in milliseconds for the run.",
                            "minimum": 0,
                        },
                        "run_cost_usd": {
                            "type": ["number", "null"],
                            "description": "Total SDK-reported run cost in USD.",
                            "minimum": 0,
                        },
                        "target_duration_seconds": {
                            "type": ["integer", "null"],
                            "description": "Requested target runtime for the final video in seconds.",
                            "minimum": 0,
                        },
                        "plan_text": {
                            "type": ["string", "null"],
                            "description": "Visible scene plan emitted before implementation.",
                        },
                        "review_summary": {
                            "type": ["string", "null"],
                            "description": "Summary of the post-render review pass.",
                        },
                        "review_approved": {
                            "type": ["boolean", "null"],
                            "description": "Whether the render review approved the video.",
                        },
                        "review_blocking_issues": {
                            "type": "array",
                            "description": "Blocking issues found during render review.",
                            "items": {"type": "string"},
                        },
                        "review_suggested_edits": {
                            "type": "array",
                            "description": "Suggested edits from the render review step.",
                            "items": {"type": "string"},
                        },
                        "review_frame_paths": {
                            "type": "array",
                            "description": "Sampled frame image paths inspected during render review.",
                            "items": {"type": "string"},
                        },
                    },
                    "required": [
                        "video_output",
                        "implemented_beats",
                        "deviations_from_plan",
                        "beat_to_narration_map",
                        "run_tool_stats",
                        "review_blocking_issues",
                        "review_suggested_edits",
                        "review_frame_paths",
                    ],
                    "additionalProperties": False,
                },
            },
        }
