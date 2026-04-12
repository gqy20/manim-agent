"""Annotation components: callouts, highlight boxes, and label groups.

Provides:
  - Callout: Corner-placed explanatory note
  - HighlightBox: SurroundingRectangle or BackgroundRectangle wrapper
  - LabelGroup: Coordinated set of labels for a diagram
"""
from __future__ import annotations

from manim import (
    DL,
    DR,
    DOWN,
    LEFT,
    RIGHT,
    UP,
    UR,
    UL,
    BackgroundRectangle,
    Brace,
    BraceText,
    MathTex,
    SurroundingRectangle,
    VGroup,
)

# manimgl-specific constants not present in ManimCE; define locally
BR = UR + DOWN  # Bottom-right diagonal
BL = UL + DOWN  # Bottom-left diagonal

from .config import BUFFER, COLOR_PALETTE, TEXT_SIZES
from .text_helpers import cjk_text, subtitle


class Callout:
    """A small explanatory note placed in a screen corner or edge.

    Used for givens, conditions, transformation notes, and legends.
    Automatically sizes and colors itself for the annotation role.

    Factory pattern (not a Mobject subclass): create via Callout.create().
    """

    @staticmethod
    def create(
        text: str,
        *,
        corner=None,
        edge=None,
        scale=None,
        color=None,
    ):
        """Create a callout text mobject positioned at a corner or edge.

        Args:
            text: Callout content (supports CJK).
            corner: Place at a corner (UL, UR, DL, DR).
            edge: Place at an edge (UP, DOWN, LEFT, RIGHT).
            scale: Override scale. Default TEXT_SIZES.annotation.
            color: Override color. Default COLOR_PALETTE.de_emphasized.

        Returns:
            A positioned Text mobject.
        """
        mob = subtitle(text, scale=scale, color=color)
        if corner is not None:
            mob.to_corner(corner, buff=BUFFER.MED_LARGE)
        elif edge is not None:
            mob.to_edge(edge, buff=BUFFER.MED_LARGE)
        return mob


class HighlightBox:
    """A highlight region around an existing mobject.

    Wraps SurroundingRectangle (outline) or BackgroundRectangle (filled)
    with sensible defaults for educational use.

    Factory pattern: create via HighlightBox.outline() or HighlightBox.filled().
    """

    @staticmethod
    def outline(
        target,
        *,
        color=None,
        buff=None,
        stroke_width=2,
    ):
        """Create an outline highlight box around target.

        Args:
            target: The mobject to highlight.
            color: Border color. Default COLOR_PALETTE.highlight (YELLOW).
            buff: Padding around target. Default BUFFER.MED_LARGE.
            stroke_width: Border thickness.

        Returns:
            A SurroundingRectangle mobject.
        """
        return SurroundingRectangle(
            target,
            color=color or COLOR_PALETTE.highlight,
            buff=buff or BUFFER.MED_LARGE,
            stroke_width=stroke_width,
        )

    @staticmethod
    def filled(
        target,
        *,
        color=None,
        buff=None,
        fill_opacity=0.15,
    ):
        """Create a filled highlight behind target.

        Use for temporary highlighting that should not distract from content.

        Args:
            target: The mobject to highlight.
            color: Fill color. Default COLOR_PALETTE.given (BLUE).
            buff: Padding around target.
            fill_opacity: Transparency level.

        Returns:
            A BackgroundRectangle mobject.
        """
        return BackgroundRectangle(
            target,
            color=color or COLOR_PALETTE.given,
            buff=buff or BUFFER.MED_LARGE,
            fill_opacity=fill_opacity,
        )


class LabelGroup:
    """Coordinated set of labels for a geometric figure or diagram.

    Creates vertex labels, angle marks, length annotations that share
    consistent styling and positioning rules.

    Usage:
        labels = LabelGroup()
        labels.add_vertex("A", point_A, direction=UL)
        labels.add_vertex("B", point_B, direction=DL)
        labels.add_angle(r"60^\\circ", angle_arc, direction=RIGHT)
        group = labels.build()  # Returns VGroup of all labels
    """

    def __init__(self) -> None:
        self._items: list[tuple] = []

    def add_vertex(self, name: str, point, direction=UL, *, scale=None):
        """Add a vertex label placed diagonally outward from a point.

        Args:
            name: Label text (e.g., "A", "B", "C").
            point: The vertex coordinate / numpy array.
            direction: Direction to offset from vertex.
            scale: Label scale override.
        """
        self._items.append(("vertex", name, point, direction, scale))

    def add_angle(self, latex: str, arc, direction=RIGHT, *, scale=None):
        """Add an angle measurement label next to an arc.

        Args:
            latex: Angle value in LaTeX (e.g., r"60^\\circ").
            arc: The Angle mobject.
            direction: Placement direction relative to arc.
            scale: Label scale override.
        """
        self._items.append(("angle", latex, arc, direction, scale))

    def add_length(self, latex: str, line, direction=DOWN, *, scale=None):
        """Add a length annotation next to a line segment.

        Args:
            latex: Length value in LaTeX (e.g., r"c = 5").
            line: The Line mobject.
            direction: Placement direction.
            scale: Label scale override.
        """
        self._items.append(("length", latex, line, direction, scale))

    def build(self) -> VGroup:
        """Build all labels into a VGroup.

        Returns:
            VGroup containing all label mobjects.
        """
        mobs = []
        for item in self._items:
            kind = item[0]
            if kind == "vertex":
                _, name, point, direction, scale = item
                mob = cjk_text(name, scale=scale or TEXT_SIZES.label)
                mob.next_to(point, direction, buff=BUFFER.SMALL)
                mobs.append(mob)
            elif kind == "angle":
                _, latex, arc, direction, scale = item
                mob = math_line(latex, scale=scale or TEXT_SIZES.label)
                mob.next_to(arc, direction, buff=BUFFER.SMALL)
                mobs.append(mob)
            elif kind == "length":
                _, latex, line, direction, scale = item
                mob = math_line(latex, scale=scale or TEXT_SIZES.label)
                mob.next_to(line, direction, buff=BUFFER.SMALL)
                mobs.append(mob)
        return VGroup(*mobs)
