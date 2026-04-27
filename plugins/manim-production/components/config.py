"""Centralized style configuration for manim-production scenes.

All values are derived from spatial-composition.md, scene-build SKILL.md,
and scene-direction SKILL.md reference documents.
Import these instead of hard-coding magic numbers in scene code.

Usage:
    from components.config import (
        BUFFER, COLOR_PALETTE, TEXT_SIZES, FONT_CONFIG,
        FONT_WEIGHTS, FONT_FAMILIES, COLOR_SHADES,
    )
    obj.next_to(ref, buff=BUFFER.MED_SMALL)
    text.set_color(COLOR_PALETTE.given)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from manim import (
    BLUE,
    BLUE_A,
    BLUE_B,
    BLUE_C,
    BLUE_D,
    BLUE_E,
    GOLD,
    GOLD_A,
    GOLD_B,
    GOLD_C,
    GOLD_D,
    GRAY,
    GRAY_A,
    GRAY_B,
    GRAY_C,
    GRAY_D,
    GREEN,
    GREEN_A,
    GREEN_B,
    GREEN_C,
    GREEN_D,
    RED,
    RED_A,
    RED_B,
    RED_C,
    RED_D,
    WHITE,
    YELLOW,
    YELLOW_A,
    YELLOW_B,
    YELLOW_C,
    YELLOW_D,
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


# ── Font Weight Constants ───────────────────────────────────────
# Pango weight names (from manim/constants.py, passed to Text())


@dataclass(frozen=True)
class FontWeights:
    """Pango font weight constants for Text() rendering."""

    NORMAL: str = "NORMAL"
    BOLD: str = "BOLD"
    THIN: str = "THIN"
    ULTRALIGHT: str = "ULTRALIGHT"
    LIGHT: str = "LIGHT"
    SEMILIGHT: str = "SEMILIGHT"
    BOOK: str = "BOOK"
    MEDIUM: str = "MEDIUM"
    SEMIBOLD: str = "SEMIBOLD"
    ULTRABOLD: str = "ULTRABOLD"
    HEAVY: str = "HEAVY"
    ULTRAHEAVY: str = "ULTRAHEAVY"


FONT_WEIGHTS: Final[FontWeights] = FontWeights()


# ── Font Family Recommendations ─────────────────────────────────
# Platform-safe CJK font names for Pango renderer


@dataclass(frozen=True)
class FontFamilies:
    """Recommended font family names by language/script category.

    These are Pango font family names (not file paths).
    Pango resolves them to actual installed fonts at runtime.
    """

    # CJK fonts — ordered by preference on Windows
    cn_primary: str = "Microsoft YaHei"       # 微软雅黑（Windows 默认 CJK）
    cn_fallback: str = "SimHei"               # 黑体（更粗，备选）
    cn_ui: str = "Microsoft YaHei UI"         # 界面字体（更清晰小字）
    cn_open_source: str = "Source Han Sans SC"  # 思源黑体（跨平台开源）
    # Latin / UI
    en_ui: str = "Segoe UI"                   # Windows 系统默认
    # Monospace
    mono: str = "Consolas"                    # Windows 等宽默认


FONT_FAMILIES: Final[FontFamilies] = FontFamilies()


# ── Font Configuration ─────────────────────────────────────────
# CJK-safe defaults for Pango renderer


@dataclass(frozen=True)
class FontConfig:
    """Font settings optimized for Chinese / Japanese / Korean text rendering."""

    default_font: str = ""  # Legacy: empty = let Pango auto-select
    math_font_size: int = 48  # Base font size for MathTex
    text_font_size: int = 36  # Base font size for Text()
    # Recommended font names (use these in new code)
    cn_font: str = FONT_FAMILIES.cn_primary   # 推荐中文字体
    en_font: str = FONT_FAMILIES.en_ui        # 推荐英文字体
    mono_font: str = FONT_FAMILIES.mono       # 推荐等宽字体
    # Default weights by element role
    title_weight: str = FONT_WEIGHTS.BOLD     # 标题字重
    body_weight: str = FONT_WEIGHTS.NORMAL    # 正文字重
    annotation_weight: str = FONT_WEIGHTS.LIGHT  # 注释/标签字重


FONT_CONFIG: Final[FontConfig] = FontConfig()


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
# Expanded to 9 levels for complete typography hierarchy


@dataclass(frozen=True)
class TextSizes:
    """Recommended scale factors by element role (9-level hierarchy).

    Base size for Text() is text_font_size (default 36).
    Scale multiplies this base to get final font_size.
    """

    # ── Display / Title tier ──
    display: float = 1.4       # 大标题（片头主标题）1.2–1.6
    heading_1: float = 1.15    # 一级标题（场景标题）1.0–1.3
    heading_2: float = 1.0     # 二级标题（beat 标题）0.9–1.15
    heading_3: float = 0.85    # 三级标题（子节标题）0.75–1.0

    # ── Body tier ──
    title: float = 1.0         # 兼容旧名 = heading_2
    body_large: float = 0.7    # 大正文（解说主体）0.6–0.85
    body: float = 0.6          # 正文（默认正文）0.45–0.7
    body_small: float = 0.5    # 小正文（次要说明）0.4–0.6

    # ── Annotation tier ──
    annotation: float = 0.45   # 注释/标签 0.35–0.6
    caption: float = 0.4       # 说明文字 0.3–0.5
    caption_small: float = 0.35  # 小说明/脚注 0.25–0.4
    fine_print: float = 0.3    # 脚注/极小文字 ≥0.25

    # ── Math formula sizes ──
    math_main: float = 1.0     # MathTex() 主公式 0.8–1.5
    math_inline: float = 0.6   # MathTex() 行内公式 0.45–0.7
    label: float = 0.5         # 坐标轴标签、图例 0.35–0.6

    # ── Safety floor ──
    readability_floor: float = 0.25  # 1080p 最小可读 scale


TEXT_SIZES: Final[TextSizes] = TextSizes()


# ── Color Shades ─────────────────────────────────────────────────
# Full 5-level shade references from manim_colors.py
# Each color has _A (lightest) through _E (darkest)


@dataclass(frozen=True)
class ColorShades:
    """Complete 5-level shade tuples for each Manim base color.

    Usage: BLUE_SHADES[0] = BLUE_A (lightest), BLUE_SHADES[4] = BLUE_E (darkest)
    Or use named access via the tuple fields.
    """

    blue: tuple = (BLUE_A, BLUE_B, BLUE_C, BLUE_D, BLUE_E)
    green: tuple = (GREEN_A, GREEN_B, GREEN_C, GREEN_D)
    yellow: tuple = (YELLOW_A, YELLOW_B, YELLOW_C, YELLOW_D)
    gold: tuple = (GOLD_A, GOLD_B, GOLD_C, GOLD_D)
    red: tuple = (RED_A, RED_B, RED_C, RED_D)
    gray: tuple = (GRAY_A, GRAY_B, GRAY_C, GRAY_D)

    @staticmethod
    def light(color_tuple: tuple) -> object:
        """Return _A (lightest) shade."""
        return color_tuple[0]

    @staticmethod
    def default(color_tuple: tuple) -> object:
        """Return _C (middle) shade — recommended default."""
        return color_tuple[2] if len(color_tuple) > 2 else color_tuple[1]

    @staticmethod
    def dark(color_tuple: tuple) -> object:
        """Return _D or _E (dark) shade for backgrounds."""
        return color_tuple[-1]


COLOR_SHADES: Final[ColorShades] = ColorShades()


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
