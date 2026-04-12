"""Manim Production Component Library.

Single import point for AI-generated scene code:
    from components import *

Or selective imports:
    from components import TitleCard, ProofStepStack, ZoneLayout

Mirrors 3b1b's manim_imports_ext.py pattern but scoped to our components.
All values are adapted for Manim Community Edition (not manimgl).
"""
from .config import (
    ANIMATION_TIMING,
    BUFFER,
    COLOR_PALETTE,
    FONT_CONFIG,
    SAFE_FRAME_MARGIN,
    SCREEN_ZONES,
    TEXT_SIZES,
)
from .text_helpers import cjk_text, cjk_title, math_line, mixed_text, subtitle
from .titles import EndingCard, TitleCard
from .formula_display import FormulaTransform, ProofStepStack, StepLabel, StepKind
from .annotations import Callout, HighlightBox, LabelGroup
from .layouts import ModeLayout, SceneMode, ZoneLayout
from .animation_helpers import (
    emphasize,
    highlight_circle,
    reveal,
    shrink_to_corner,
    transform_step,
    write_in,
)
from .scene_templates import TeachingScene

__version__ = "0.1.0"

__all__ = [
    # Config
    "BUFFER",
    "COLOR_PALETTE",
    "TEXT_SIZES",
    "SCREEN_ZONES",
    "FONT_CONFIG",
    "ANIMATION_TIMING",
    "SAFE_FRAME_MARGIN",
    # Text helpers
    "cjk_text",
    "cjk_title",
    "math_line",
    "mixed_text",
    "subtitle",
    # Titles
    "TitleCard",
    "EndingCard",
    # Formula display
    "ProofStepStack",
    "FormulaTransform",
    "StepLabel",
    "StepKind",
    # Annotations
    "Callout",
    "HighlightBox",
    "LabelGroup",
    # Layouts
    "ZoneLayout",
    "ModeLayout",
    "SceneMode",
    # Animation helpers
    "reveal",
    "write_in",
    "emphasize",
    "highlight_circle",
    "transform_step",
    "shrink_to_corner",
    # Scene templates
    "TeachingScene",
]
