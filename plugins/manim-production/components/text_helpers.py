"""CJK-safe text creation helpers for Manim Community Edition.

Every helper enforces the rule matrix from scene-build SKILL.md:
  - Chinese text -> Text() (Pango, native CJK support)
  - Math formulas -> MathTex() (LaTeX, no Chinese allowed)
  - Mixed content -> VGroup of separate mobjects

Usage:
    from components.text_helpers import cjk_text, math_line, mixed_text, subtitle

    title = cjk_title("勾股定理")
    formula = math_line(r"x = \\sqrt{2}")
    line = mixed_text("其中", r"x = \\sqrt{2}")
    sub = subtitle("第一步：作辅助线")
"""
from __future__ import annotations

from manim import DOWN, MathTex, RIGHT, Text, VGroup

from .config import (
    COLOR_PALETTE,
    FONT_CONFIG,
    FONT_WEIGHTS,
    TEXT_SIZES,
)


def cjk_text(
    content: str,
    *,
    scale: float | None = None,
    color=None,
    font: str | None = None,
    weight: str | None = None,
    slant: str | None = None,
    **kwargs,
) -> Text:
    """Create Chinese / Japanese / Korean text using Pango renderer.

    This is the ONLY correct way to render CJK characters in ManimCE.
    Never use Tex() or MathTex() for strings containing CJK characters.

    Args:
        content: The text string (may contain CJK characters).
        scale: Optional scale factor. Defaults to TEXT_SIZES.body.
        color: Text color. Defaults to COLOR_PALETTE.neutral.
        font: Custom font name. None uses FONT_CONFIG.cn_font.
        weight: Pango font weight (e.g., "BOLD", "LIGHT"). None uses default.
        slant: Pango font slant (e.g., "ITALIC"). None uses default.
        **kwargs: Additional arguments passed to Text().

    Returns:
        A Text mobject ready for positioning and animation.
    """
    resolved_font = font if font is not None else FONT_CONFIG.cn_font
    text_kwargs: dict = {}
    if resolved_font:
        text_kwargs["font"] = resolved_font
    if weight is not None:
        text_kwargs["weight"] = weight
    if slant is not None:
        text_kwargs["slant"] = slant
    text_kwargs.update(kwargs)

    mob = Text(content, **text_kwargs)
    if color is not None:
        mob.set_color(color)
    else:
        mob.set_color(COLOR_PALETTE.neutral)
    mob.scale(scale if scale is not None else TEXT_SIZES.body)
    return mob


def cjk_title(
    content: str,
    *,
    scale: float | None = None,
    color=None,
    weight: str | None = None,
    **kwargs,
) -> Text:
    """Create a CJK title using larger default scale and BOLD weight.

    Args:
        content: Title text string.
        scale: Scale factor. Defaults to TEXT_SIZES.heading_2 (1.0).
        color: Title color. Defaults to neutral.
        weight: Font weight. Defaults to BOLD.
        **kwargs: Additional arguments passed to Text().

    Returns:
        A Text mobject sized for title-zone placement.
    """
    return cjk_text(
        content,
        scale=scale if scale is not None else TEXT_SIZES.heading_2,
        color=color,
        weight=weight if weight is not None else FONT_WEIGHTS.BOLD,
        **kwargs,
    )


def math_line(
    latex: str,
    *,
    scale: float | None = None,
    color=None,
    **kwargs,
) -> MathTex:
    """Create a mathematical formula using LaTeX.

    IMPORTANT: Do NOT pass CJK characters in latex string.
    For mixed Chinese + math, use mixed_text() instead.

    Args:
        latex: Pure LaTeX / math string (e.g., r"a^2 + b^2 = c^2").
        scale: Scale factor. Defaults to TEXT_SIZES.math_main.
        color: Formula color. Defaults to COLOR_PALETTE.given (BLUE).
        **kwargs: Additional arguments passed to MathTex().

    Returns:
        A MathTex mobject.
    """
    mob = MathTex(latex, **kwargs)
    if color is not None:
        mob.set_color(color)
    else:
        mob.set_color(COLOR_PALETTE.given)
    mob.scale(scale if scale is not None else TEXT_SIZES.math_main)
    return mob


def mixed_text(
    chinese_part: str,
    math_part: str,
    *,
    direction=RIGHT,
    buff=0.1,
    chinese_scale=None,
    math_scale=None,
    weight=None,
    slant=None,
    **kwargs,
) -> VGroup:
    """Combine CJK text and math formula into a horizontal group.

    This solves the common pattern from scene-build SKILL.md:
        VGroup(Text("其中"), MathTex(r"x = \\sqrt{2}")).arrange(RIGHT, buff=0.1)

    Args:
        chinese_part: Chinese text (rendered via Text / Pango).
        math_part: LaTeX math string (rendered via MathTex).
        direction: Arrangement direction. Default RIGHT (horizontal).
        buff: Spacing between parts. Default 0.1 (SMALL_BUFF).
        chinese_scale: Override scale for Chinese part.
        math_scale: Override scale for math part.
        weight: Font weight for the Chinese part.
        slant: Font slant for the Chinese part.
        **kwargs: Additional arrangement keyword arguments.

    Returns:
        A VGroup containing both parts, arranged horizontally.
    """
    cn = cjk_text(chinese_part, scale=chinese_scale, weight=weight, slant=slant)
    mt = math_line(math_part, scale=math_scale)
    return VGroup(cn, mt).arrange(direction, buff=buff, **kwargs)


def subtitle(
    content: str,
    *,
    scale: float | None = None,
    color=None,
    weight: str | None = None,
    **kwargs,
) -> Text:
    """Create a subtitle / caption text at annotation size with LIGHT weight.

    Args:
        content: Subtitle text (may contain CJK).
        scale: Scale factor. Defaults to TEXT_SIZES.annotation (0.45).
        color: Text color. Defaults to de-emphasized gray.
        weight: Font weight. Defaults to LIGHT.
        **kwargs: Additional arguments passed to Text().

    Returns:
        A small Text mobject suitable for footers or captions.
    """
    return cjk_text(
        content,
        scale=scale if scale is not None else TEXT_SIZES.annotation,
        color=color if color is not None else COLOR_PALETTE.de_emphasized,
        weight=weight if weight is not None else FONT_WEIGHTS.LIGHT,
        **kwargs,
    )
