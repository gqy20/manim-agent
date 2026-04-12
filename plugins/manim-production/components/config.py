"""Centralized style configuration for manim-production scenes.

All values are derived from spatial-composition.md, scene-build SKILL.md,
and scene-direction SKILL.md reference documents.
Import these instead of hard-coding magic numbers in scene code.

Usage:
    from components.config import BUFFER, COLOR_PALETTE, TEXT_SIZES
    obj.next_to(ref, buff=BUFFER.MED_SMALL)
    text.set_color(COLOR_PALETTE.given)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from manim import (
    BLUE,
    BLUE_B,
    BLUE_C,
    BLUE_D,
    BLUE_E,
    GOLD,
    GRAY,
    GREEN,
    RED,
    WHITE,
    YELLOW,
)


# ── Buffer Constants ──────────────────────────────────────────────
# Re-exports of ManimCE built-in buffer constants under a namespace.
# Values are identical; this class provides BUFFER.SMALL style access
# so all project constants share one import pattern (components.config).
# From spatial-composition.md "Buffer Values" table.

from manim import LARGE_BUFF as _MANIM_LARGE_BUFF
from manim import MED_LARGE_BUFF as _MANIM_MED_LARGE_BUFF
from manim import MED_SMALL_BUFF as _MANIM_MED_SMALL_BUFF
from manim import SMALL_BUFF as _MANIM_SMALL_BUFF


class BUFFER:
    """Namespace wrapper around ManimCE's built-in buffer constants.

    Provides BUFFER.SMALL instead of importing SMALL_BUFF directly,
    keeping a consistent import pattern for all style constants.
    """

    SMALL: float = _MANIM_SMALL_BUFF  # Tight spacing (adjacent related items)
    MED_SMALL: float = _MANIM_MED_SMALL_BUFF  # Default next_to() gap
    MED_LARGE: float = _MANIM_MED_LARGE_BUFF  # Edge / corner margin
    LARGE: float = _MANIM_LARGE_BUFF  # Section separation


# ── Color Palette ─────────────────────────────────────────────────
# From spatial-composition.md "Color Palette for Educational Content"


@dataclass(frozen=True)
class ColorPalette:
    """Semantic color assignments for educational content."""

    given: object = BLUE  # Input values, original state
    highlight: object = YELLOW  # Focal emphasis, key results
    conclusion: object = GREEN  # Correct answers, final states
    transformation: object = RED  # Changes, errors, warnings
    neutral: object = WHITE  # Neutral text on dark background
    de_emphasized: object = GRAY  # Secondary info, faded elements


COLOR_PALETTE: Final[ColorPalette] = ColorPalette()


# ── Text Size Scale ───────────────────────────────────────────────
# From spatial-composition.md "Text and Formula Sizes" table


@dataclass(frozen=True)
class TextSizes:
    """Recommended scale factors by element role."""

    title: float = 1.0  # Text() title; range 0.8-1.2
    body: float = 0.6  # Text() body; range 0.45-0.7
    annotation: float = 0.45  # Side annotations; range 0.35-0.6
    math_main: float = 1.0  # MathTex() main formula; range 0.8-1.5
    math_inline: float = 0.6  # MathTex() inline / side; range 0.45-0.7
    label: float = 0.5  # Axis labels, legends; range 0.35-0.6
    readability_floor: float = 0.35  # Minimum scale at 1080p


TEXT_SIZES: Final[TextSizes] = TextSizes()


# ── Font Configuration ─────────────────────────────────────────────
# CJK-safe defaults for Pango renderer


@dataclass(frozen=True)
class FontConfig:
    """Font settings optimized for Chinese / Japanese / Korean text rendering."""

    default_font: str = ""  # Empty = let Pango auto-select CJK font
    math_font_size: int = 48  # Base font size for MathTex
    text_font_size: int = 36  # Base font size for Text()


FONT_CONFIG: Final[FontConfig] = FontConfig()


# ── Screen Zones ───────────────────────────────────────────────────
# From spatial-composition.md "Screen Zone Map"


@dataclass(frozen=True)
class ScreenZones:
    """Named screen regions with coordinate boundaries."""

    TITLE_Y_MIN: float = 2.5  # Above this = title zone
    MAIN_Y_MAX: float = 2.5  # Below title, above footer
    MAIN_Y_MIN: float = -2.5
    MAIN_X_MAX: float = 5.0
    MAIN_X_MIN: float = -5.0
    ANNOTATION_X_THRESHOLD: float = 4.0  # |x| > this = annotation zone
    FOOTER_Y_MAX: float = -2.5  # Below this = footer zone


SCREEN_ZONES: Final[ScreenZones] = ScreenZones()


# ── Safe Frame Margin ─────────────────────────────────────────────
# Used by layout_safety.py and any frame-bounds checking

SAFE_FRAME_MARGIN: Final[float] = 0.25


# ── Animation Duration Defaults ────────────────────────────────────
# From scene-build SKILL.md "Animation duration bounds" table


@dataclass(frozen=True)
class AnimationTiming:
    """Default run_time ranges by animation type (seconds)."""

    fade_in: tuple[float, float, float] = (0.3, 0.65, 1.5)
    create: tuple[float, float, float] = (0.5, 1.25, 3.0)
    write: tuple[float, float, float] = (1.0, 1.75, 4.0)
    transform: tuple[float, float, float] = (1.0, 2.0, 4.0)
    grow: tuple[float, float, float] = (0.4, 1.0, 2.0)
    indicate: tuple[float, float, float] = (0.3, 0.75, 1.5)
    shift: tuple[float, float, float] = (0.3, 0.75, 2.0)
    wait: tuple[float, float, float] = (0.1, 0.55, 1.5)


ANIMATION_TIMING: Final[AnimationTiming] = AnimationTiming()
