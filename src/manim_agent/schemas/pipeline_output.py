"""Final PipelineOutput schema - merged result of all phases.

This schema serves as the unified output format for the entire staged pipeline.
It stores both top-level delivery fields and phase sub-objects for traceability.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from .phase1_planning import BuildSpec, Phase1PlanningOutput
from .phase2_implementation import Phase2ImplementationOutput
from .phase3_render_review import Phase3RenderReviewOutput
from .phase4_tts import Phase4TTSOutput
from .phase5_mux import Phase5MuxOutput


class PipelineOutput(BaseModel):
    """Final merged output from the entire pipeline.

    Stores top-level delivery fields and phase-specific outputs.
    """

    video_output: str | None = Field(
        default=None,
        description="Path to the rendered scene video before final mux.",
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
        description="Narration text for TTS. Default is Simplified Chinese if not specified.",
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
        description="Explicit deviations from the approved build plan/context, if any.",
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
    render_mode: str | None = Field(
        default=None,
        description="Visual render delivery mode, such as full or segments.",
    )
    segment_render_complete: bool | None = Field(
        default=None,
        description="Whether beat-level segment rendering completed for every planned beat.",
    )
    beats: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Structured beat records for audio orchestration and timeline rendering.",
    )
    audio_segments: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Structured per-beat audio assets generated during audio orchestration.",
    )
    timeline_path: str | None = Field(
        default=None,
        description="Path to the resolved beat timeline JSON file, if generated.",
    )
    timeline_total_duration_seconds: float | None = Field(
        default=None,
        description="Resolved duration of the concatenated beat timeline in seconds.",
        ge=0,
    )
    segment_render_plan_path: str | None = Field(
        default=None,
        description="Path to the generated segment render plan JSON file, if prepared.",
    )
    segment_video_paths: list[str] = Field(
        default_factory=list,
        description="Reserved output paths for future beat-level rendered video segments.",
    )
    audio_concat_path: str | None = Field(
        default=None,
        description="Path to the concatenated narration master audio file, if generated.",
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
    run_cost_cny: float | None = Field(
        default=None,
        description="Estimated total Claude Agent SDK token cost in CNY.",
        ge=0,
    )
    target_duration_seconds: int | None = Field(
        default=None,
        description="Requested target runtime for the final video in seconds.",
        ge=0,
    )
    plan_text: str | None = Field(
        default=None,
        description="Build plan/context derived from the Phase 1 build_spec.",
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
    review_frame_analyses: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Per-frame visual analysis details from render review.",
    )
    review_vision_analysis_used: bool | None = Field(
        default=None,
        description="Whether AI vision analysis was used during render review.",
    )
    intro_requested: bool | None = Field(
        default=None,
        description="Whether an intro segment was requested for this run.",
    )
    outro_requested: bool | None = Field(
        default=None,
        description="Whether an outro segment was requested for this run.",
    )
    intro_spec: dict[str, Any] | None = Field(
        default=None,
        description="Structured intro specification (title, style, duration, colors).",
    )
    outro_spec: dict[str, Any] | None = Field(
        default=None,
        description="Structured outro specification (message, style, duration, colors).",
    )
    intro_video_path: str | None = Field(
        default=None,
        description="Path to the rendered intro MP4 segment, if generated.",
    )
    outro_video_path: str | None = Field(
        default=None,
        description="Path to the rendered outro MP4 segment, if generated.",
    )
    intro_outro_backend: str | None = Field(
        default=None,
        description="Backend used for intro/outro generation: 'revideo' or 'manim'.",
    )

    phase1_planning: Phase1PlanningOutput | None = Field(
        default=None,
        description="Phase 1 (planning) output - structured planning result.",
    )
    phase2_implementation: Phase2ImplementationOutput | None = Field(
        default=None,
        description="Phase 2 (implementation) output - scene build result.",
    )
    phase3_render_review: Phase3RenderReviewOutput | None = Field(
        default=None,
        description="Phase 3 (render review) output - quality check result.",
    )
    phase4_tts: Phase4TTSOutput | None = Field(
        default=None,
        description="Phase 4 (TTS) output - text-to-speech result.",
    )
    phase5_mux: Phase5MuxOutput | None = Field(
        default=None,
        description="Phase 5 (mux) output - final video assembly result.",
    )

    @field_validator("video_output")
    @classmethod
    def _video_output_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip():
            raise ValueError("video_output must not be blank")
        return value


__all__ = [
    "BuildSpec",
    "Phase1PlanningOutput",
    "Phase2ImplementationOutput",
    "Phase3RenderReviewOutput",
    "Phase4TTSOutput",
    "Phase5MuxOutput",
    "PipelineOutput",
]
