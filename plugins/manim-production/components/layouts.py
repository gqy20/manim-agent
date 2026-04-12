"""Zone-based layout templates for different scene modes.

Implements the four per-mode layout templates from spatial-composition.md:
  - ProofWalkthrough: Vertical stack, left-aligned, diagram on right
  - FunctionVisualization: Graph-centered, axes as frame
  - GeometryConstruction: Central figure, peripheral marks
  - ConceptExplainer: Centered diagram with corner callouts

Each layout is a builder (not a Scene) that returns positioned mobjects.
The caller places them into their Scene.construct() and animates as needed.
"""
from __future__ import annotations

from enum import Enum

from manim import (
    DOWN,
    LEFT,
    ORIGIN,
    RIGHT,
    UP,
    VGroup,
)

from .config import BUFFER, SCREEN_ZONES, TEXT_SIZES
from .formula_display import ProofStepStack, StepKind
from .text_helpers import cjk_title, subtitle


class SceneMode(Enum):
    """Scene mode determines which layout template to use."""

    PROOF_WALKTHROUGH = "proof_walkthrough"
    FUNCTION_VISUALIZATION = "function_visualization"
    GEOMETRY_CONSTRUCTION = "geometry_construction"
    CONCEPT_EXPLAINER = "concept_explainer"
    QUICK_DEMO = "quick_demo"


class ZoneLayout:
    """Places content into predefined screen zones according to the zone map.

    Provides methods for placing content into:
      - Title zone (y > 2.5)
      - Main content zone (center)
      - Left / right annotation zones (|x| > 4)
      - Footer zone (y < -2.5)

    Usage:
        layout = ZoneLayout()
        layout.set_title("Pythagorean Theorem")
        layout.set_main_content(formula_vgroup)
        layout.left_annotation(given_label)
        layout.right_annotation(result_label)
        all_mobjects = layout.build()
    """

    def __init__(self) -> None:
        self._title = None
        self._main = None
        self._left_annots: list = []
        self._right_annots: list = []
        self._footer = None

    def set_title(self, title_mob):
        """Place a mobject in the title zone."""
        self._title = title_mob
        if self._title is not None:
            self._title.to_edge(UP, buff=BUFFER.MED_LARGE)

    def set_main_content(self, mob):
        """Place a mobject in the main content zone (center)."""
        self._main = mob

    def add_left_annotation(self, mob):
        """Add an annotation to the left zone."""
        mob.to_edge(LEFT, buff=BUFFER.LARGE)
        self._left_annots.append(mob)

    def add_right_annotation(self, mob):
        """Add an annotation to the right zone."""
        mob.to_edge(RIGHT, buff=BUFFER.LARGE)
        self._right_annots.append(mob)

    def set_footer(self, mob):
        """Place a mobject in the footer zone."""
        self._footer = mob
        if self._footer is not None:
            self._footer.to_edge(DOWN, buff=BUFFER.MED_LARGE)

    def build(self) -> dict:
        """Return all positioned mobjects as a dict.

        Returns:
            Dict with keys: 'title', 'main', 'left_annotations',
            'right_annotations', 'footer' (values may be None).
        """
        return {
            "title": self._title,
            "main": self._main,
            "left_annotations": (
                VGroup(*self._left_annots) if self._left_annots else None
            ),
            "right_annotations": (
                VGroup(*self._right_annots) if self._right_annots else None
            ),
            "footer": self._footer,
        }


class ModeLayout:
    """Selects and applies the correct layout template for a given scene mode.

    This is the programmatic equivalent of choosing the right layout table
    from spatial-composition.md based on the task mode.

    Usage:
        layout = ModeLayout(SceneMode.PROOF_WALKTHROUGH)
        layout.set_title("Proof: Pythagorean Theorem")
        layout.add_proof_step("given", r"a^2 + b^2 = c^2 ?")
        layout.set_diagram(triangle_figure)
        result = layout.build()
    """

    def __init__(self, mode: SceneMode) -> None:
        self._mode = mode
        self._zone = ZoneLayout()
        self._proof_stack: ProofStepStack | None = None
        self._diagram = None

    @property
    def mode(self) -> SceneMode:
        return self._mode

    def set_title(self, title_text: str):
        """Set the scene title (all modes)."""
        self._zone.set_title(cjk_title(title_text))

    def add_proof_step(
        self, kind_str: str, latex: str, *, step_num: int | None = None
    ):
        """Add a proof step (PROOF_WALKTHROUGH mode).

        Args:
            kind_str: One of "given", "step", "goal", "therefore", "qed".
            latex: LaTeX formula for this step.
            step_num: Optional ordinal for STEP kind.
        """
        if self._proof_stack is None:
            self._proof_stack = ProofStepStack()
        kind_map = {
            "given": StepKind.GIVEN,
            "step": StepKind.STEP,
            "goal": StepKind.GOAL,
            "therefore": StepKind.THEREFORE,
            "qed": StepKind.QED,
        }
        kind = kind_map.get(kind_str.lower(), StepKind.STEP)
        self._proof_stack.add_step(kind, latex, step_number=step_num)

    def set_diagram(self, diagram_mob):
        """Set the main diagram / figure (PROOF or GEOMETRY mode)."""
        self._diagram = diagram_mob
        if self._mode == SceneMode.PROOF_WALKTHROUGH:
            diagram_mob.to_edge(RIGHT, buff=BUFFER.LARGE)
        elif self._mode == SceneMode.GEOMETRY_CONSTRUCTION:
            diagram_mob.scale(0.75)
            diagram_mob.move_to(ORIGIN)

    def build(self) -> dict:
        """Build and position all content according to the mode template.

        Returns:
            Dict of positioned mobjects ready for animation.
        """
        result = dict(self._zone.build())

        if (
            self._mode == SceneMode.PROOF_WALKTHROUGH
            and self._proof_stack
        ):
            proof_group = self._proof_stack.build(to_edge=(LEFT, BUFFER.LARGE))
            result["proof_steps"] = proof_group
            result["main"] = proof_group

        if self._diagram:
            result["diagram"] = self._diagram

        return result
