"""Unified schema registry for all pipeline phases.

Each phase has its own dedicated schema defined in this package.
The PhaseSchemaRegistry provides:
- Centralized lookup by phase name
- Auto-generated JSON schema from Pydantic models
- Backward compatibility with existing code

Usage:
    from manim_agent.schemas import PhaseSchemaRegistry

    # Get JSON schema for a specific phase
    schema = PhaseSchemaRegistry.output_format_schema("phase1_planning")

    # Get the Pydantic model class
    model = PhaseSchemaRegistry.get_model("phase1_planning")

    # List all available phases
    phases = PhaseSchemaRegistry.available_phases()
"""

from __future__ import annotations

from typing import Any

from .phase1_planning import BuildSpec, BuildSpecBeat, Phase1PlanningOutput
from .phase2_implementation import Phase2ImplementationOutput
from .phase3_render_review import FrameAnalysis, Phase3RenderReviewOutput
from .phase4_tts import Phase4TTSOutput
from .phase5_mux import Phase5MuxOutput
from .pipeline_output import PipelineOutput


class PhaseSchemaRegistry:
    """Registry for all pipeline phase schemas.

    Provides centralized access to phase output schemas with
    auto-generated JSON schema from Pydantic models.
    """

    _SCHEMAS: dict[
        str,
        type[
            Phase1PlanningOutput
            | Phase2ImplementationOutput
            | Phase3RenderReviewOutput
            | Phase4TTSOutput
            | Phase5MuxOutput
            | PipelineOutput
        ],
    ] = {
        "phase1_planning": Phase1PlanningOutput,
        "phase2_implementation": Phase2ImplementationOutput,
        "phase3_render_review": Phase3RenderReviewOutput,
        "phase4_tts": Phase4TTSOutput,
        "phase5_mux": Phase5MuxOutput,
        "pipeline_output": PipelineOutput,
    }

    _PHASE_NAMES: dict[str, str] = {
        "phase1": "phase1_planning",
        "phase2": "phase2_implementation",
        "phase3": "phase3_render_review",
        "phase4": "phase4_tts",
        "phase5": "phase5_mux",
        "planning": "phase1_planning",
        "implementation": "phase2_implementation",
        "render_review": "phase3_render_review",
        "tts": "phase4_tts",
        "mux": "phase5_mux",
        "pipeline": "pipeline_output",
    }

    @classmethod
    def available_phases(cls) -> list[str]:
        """Return list of all registered phase names."""
        return list(cls._SCHEMAS.keys())

    @classmethod
    def resolve_phase_name(cls, name: str) -> str:
        """Resolve short phase name to full schema name.

        Examples:
            "phase1" -> "phase1_planning"
            "planning" -> "phase1_planning"
            "phase1_planning" -> "phase1_planning"
        """
        if name in cls._SCHEMAS:
            return name
        return cls._PHASE_NAMES.get(name, name)

    @classmethod
    def get_model(cls, phase: str) -> type:
        """Get the Pydantic model class for a phase.

        Args:
            phase: Phase name (e.g., "phase1", "phase1_planning", "planning")

        Returns:
            The Pydantic model class for that phase.

        Raises:
            KeyError: If phase is not found in registry.
        """
        resolved = cls.resolve_phase_name(phase)
        if resolved not in cls._SCHEMAS:
            available = ", ".join(cls.available_phases())
            raise KeyError(f"Unknown phase: {phase!r}. Available phases: {available}")
        return cls._SCHEMAS[resolved]

    @classmethod
    def output_format_schema(cls, phase: str) -> dict[str, Any]:
        """Generate Claude Agent SDK compatible output_format schema for a phase.

        Auto-generates the JSON schema from the Pydantic model's metadata.

        Args:
            phase: Phase name (e.g., "phase1", "phase1_planning", "planning")

        Returns:
            Dict suitable for ClaudeAgentOptions.output_format.
        """
        model = cls.get_model(phase)
        schema_name = cls.resolve_phase_name(phase)

        json_schema = model.model_json_schema()

        return {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": json_schema,
            },
        }

    @classmethod
    def validate(cls, phase: str, data: dict[str, Any]) -> Any:
        """Validate data against a phase's schema.

        Args:
            phase: Phase name.
            data: Raw data dict to validate.

        Returns:
            Validated Pydantic model instance.
        """
        model = cls.get_model(phase)
        return model.model_validate(data)

    @classmethod
    def merge_phase_output(
        cls,
        pipeline_output: PipelineOutput,
        phase: str,
        phase_data: dict[str, Any],
    ) -> PipelineOutput:
        """Merge a phase's output into the pipeline output.

        Args:
            pipeline_output: Current pipeline output state.
            phase: Phase name (e.g., "phase1", "phase2").
            phase_data: Raw data from that phase.

        Returns:
            Updated pipeline output with the phase's data merged in.
        """
        resolved = cls.resolve_phase_name(phase)
        if resolved == "phase1_planning":
            pipeline_output.phase1_planning = Phase1PlanningOutput.model_validate(phase_data)
        elif resolved == "phase2_implementation":
            pipeline_output.phase2_implementation = Phase2ImplementationOutput.model_validate(
                phase_data
            )
        elif resolved == "phase3_render_review":
            pipeline_output.phase3_render_review = Phase3RenderReviewOutput.model_validate(
                phase_data
            )
        elif resolved == "phase4_tts":
            pipeline_output.phase4_tts = Phase4TTSOutput.model_validate(phase_data)
        elif resolved == "phase5_mux":
            pipeline_output.phase5_mux = Phase5MuxOutput.model_validate(phase_data)
        return pipeline_output


# ── Backward compatibility aliases ────────────────────────────────────────────

ScenePlanOutput = Phase1PlanningOutput
RenderReviewOutput = Phase3RenderReviewOutput


__all__ = [
    "PhaseSchemaRegistry",
    "BuildSpec",
    "BuildSpecBeat",
    "FrameAnalysis",
    "Phase1PlanningOutput",
    "Phase2ImplementationOutput",
    "Phase3RenderReviewOutput",
    "Phase4TTSOutput",
    "Phase5MuxOutput",
    "PipelineOutput",
    "ScenePlanOutput",
    "RenderReviewOutput",
]
