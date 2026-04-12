"""Formula display components for proof walkthroughs and equation animations.

Provides:
  - ProofStepStack: Vertically stacked derivation steps with labels
  - FormulaTransform: Animated equation transformation with old-version persistence
  - StepLabel: "Given", "Step 1", "Therefore" labels for proof lines

These implement the patterns from spatial-composition.md Proof Walkthrough layout
and scene-direction SKILL.md shrink-to-corner visual persistence rule.
"""
from __future__ import annotations

from enum import Enum
from typing import Iterable

from manim import (
    DL,
    DR,
    DOWN,
    FadeOut,
    LEFT,
    MathTex,
    ReplacementTransform,
    RIGHT,
    UP,
    VGroup,
)
from manim.animation.creation import Write

from .config import BUFFER, COLOR_PALETTE, TEXT_SIZES
from .text_helpers import cjk_text, math_line, subtitle


class StepKind(Enum):
    """Predefined label types for proof steps."""

    GIVEN = "Given"
    STEP = "Step"
    GOAL = "Goal"
    THEREFORE = "Therefore"
    QED = "Q.E.D."


STEP_LABEL_MAP: dict[StepKind, str] = {
    StepKind.GIVEN: "已知",
    StepKind.STEP: "步骤",
    StepKind.GOAL: "求证",
    StepKind.THEREFORE: "因此",
    StepKind.QED: "证毕",
}


def StepLabel(kind: StepKind, step_number: int | None = None):
    """Create a proof-step label mobject.

    Args:
        kind: The type of step (GIVEN, STEP, GOAL, etc.).
        step_number: Optional number for STEP kind (e.g., "步骤 1").

    Returns:
        A small Text mobject with the label.
    """
    base = STEP_LABEL_MAP.get(kind, kind.value)
    text = f"{base} {step_number}" if step_number is not None else base
    return subtitle(text, color=COLOR_PALETTE.highlight)


class ProofStepStack:
    """Vertically stacked proof derivation with labeled steps.

    Manages a column of MathTex formulas, left-aligned, with optional
    step labels on the left side. Implements the Proof Walkthrough layout
    from spatial-composition.md.

    Usage:
        stack = ProofStepStack()
        stack.add_step(StepKind.GIVEN, r"a^2 + b^2 = c^2 ?")
        stack.add_step(StepKind.STEP, r"a^2 + b^2 = c^2 \\cdot \\sin^2(\\theta)", step_num=1)
        stack.add_step(StepKind.STEP, r"= c^2", step_num=2)

        # Get the assembled VGroup for positioning
        group = stack.build(to_edge=(LEFT, BUFFER.LARGE))

        # Or animate step-by-step:
        stack.animate_write(scene, run_time_per_step=1.5)
    """

    def __init__(self) -> None:
        self._steps: list[tuple[StepKind, str, int | None]] = []
        self._formulas: list[MathTex] = []
        self._labels: list = []

    def add_step(
        self,
        kind: StepKind,
        latex: str,
        *,
        step_number: int | None = None,
    ) -> None:
        """Add a derivation step.

        Args:
            kind: Step classification.
            latex: LaTeX formula for this step.
            step_number: Optional ordinal for STEP kind.
        """
        self._steps.append((kind, latex, step_number))

    def build(self, **position_kwargs) -> VGroup:
        """Build and position the complete step stack.

        Args:
            **position_kwargs: Positioning kwargs passed to final VGroup
                               (e.g., to_edge=(LEFT, BUFFER.LARGE)).

        Returns:
            A VGroup containing all labels and formulas, positioned.
        """
        self._formulas = [
            math_line(latex, scale=TEXT_SIZES.math_inline)
            for _, latex, _ in self._steps
            if latex  # Skip label-only steps like QED
        ]
        self._labels = [
            StepLabel(kind, num)
            for kind, _, num in self._steps
        ]

        formula_col = VGroup(*self._formulas).arrange(
            DOWN,
            aligned_edge=LEFT,
            buff=BUFFER.MED_SMALL,
        )
        label_col = VGroup(*self._labels).arrange(
            DOWN,
            aligned_edge=RIGHT,
            buff=BUFFER.MED_SMALL,
        )
        label_col.next_to(formula_col, LEFT, buff=BUFFER.SMALL)

        full_group = VGroup(label_col, formula_col)
        if position_kwargs:
            method_name = list(position_kwargs.keys())[0]
            method_args = list(position_kwargs.values())[0]
            if isinstance(method_args, tuple):
                getattr(full_group, method_name)(*method_args)
            else:
                getattr(full_group, method_name)(method_args)
        return full_group

    def animate_write(self, scene, *, run_time_per_step: float = 1.5):
        """Animate writing each formula sequentially.

        Calls scene.play() for each formula with Write animation.

        Args:
            scene: The Scene instance to animate on.
            run_time_per_step: Seconds per step animation.
        """
        if not self._formulas:
            self.build()
        for formula in self._formulas:
            scene.play(Write(formula), run_time=run_time_per_step)
            scene.wait(0.3)


def FormulaTransform(
    original: MathTex,
    target_latex: str,
    *,
    run_time: float = 2.0,
    persist_old: bool = True,
    persist_corner=DL,
    persist_scale: float = 0.45,
    **kwargs,
) -> tuple:
    """Animate a formula transformation with optional old-version persistence.

    Implements the shrink-to-corner visual persistence pattern from
    scene-direction SKILL.md section 5E. After transforming a formula,
    the old version shrinks to a corner so viewers can glance back.

    Args:
        original: The existing MathTex mobject to transform FROM.
        target_latex: LaTeX string for the new formula.
        run_time: Animation duration. Default 2.0 s.
        persist_old: If True, keep a shrunken copy in a corner.
        persist_corner: Which corner to shrink toward. Default DL.
        persist_scale: Scale factor for persisted copy. Default 0.45.
        **kwargs: Extra args passed to ReplacementTransform.

    Returns:
        Tuple of (new_formula_mobject, old_copy_or_None).
    """
    target = math_line(target_latex)
    # Match scale to original
    if original.get_height() > 0:
        target.scale(original.get_height() / target.get_height())

    old_copy = None
    if persist_old:
        old_copy = original.copy()

    anim = ReplacementTransform(original, target, run_time=run_time, **kwargs)
    return target, old_copy, anim
