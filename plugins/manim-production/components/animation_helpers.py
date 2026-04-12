"""Preset animation helpers with semantic naming.

Instead of remembering which rate_func pairs with which animation type,
call a semantic function that returns the right configuration:

    reveal(obj)              # GrowFromCenter with ease_out_cubic
    emphasize(obj)           # Indicate with ease_out_back
    transform_step(a, b)    # ReplacementTransform with ease_in_out_sine
    shrink_to_corner(obj)    # Scale + move to corner for persistence

These encode the Motion=Meaning mapping from scene-direction SKILL.md
and the rate function guide from animation-craft.md.
"""
from __future__ import annotations

from manim import (
    DL,
    Circumscribe,
    Create,
    FadeIn,
    GrowFromCenter,
    Indicate,
    ReplacementTransform,
    ShowPassingFlash,
    Write,
)
from manim.utils.rate_functions import (
    ease_out_back,
    ease_out_cubic,
    ease_in_out_sine,
    linear,
    smooth,
)

from .config import ANIMATION_TIMING, BUFFER


def reveal(mobject, *, run_time=None, rate_func=None):
    """Reveal a new concept with appropriate easing.

    Maps to: Introducing a **new concept** -> GrowFromCenter (scene-direction).
    Default: ease_out_cubic (fast start, gentle stop feels natural).

    Args:
        mobject: The mobject to reveal.
        run_time: Override duration. Default from ANIMATION_TIMING.grow.
        rate_func: Override easing. Default ease_out_cubic.

    Returns:
        An animation instance ready for self.play().
    """
    _min, _rec, _max = ANIMATION_TIMING.grow
    rt = run_time or _rec
    rf = rate_func or ease_out_cubic
    return GrowFromCenter(mobject, run_time=rt, rate_func=rf)


def write_in(mobject, *, run_time=None, rate_func=None):
    """Write / draw a mobject (for derivations, step-by-step processes).

    Maps to: A **derivation / step-by-step** process -> Write (scene-direction).

    Args:
        mobject: The mobject to write in.
        run_time: Override duration. Default from ANIMATION_TIMING.write.
        rate_func: Override easing. Default linear (drawing feels mechanical).

    Returns:
        A Write animation instance.
    """
    _min, _rec, _max = ANIMATION_TIMING.write
    rt = run_time or _rec
    rf = rate_func or linear
    return Write(mobject, run_time=rt, rate_func=rf)


def emphasize(mobject, *, run_time=None, rate_func=None):
    """Emphasize an existing key result.

    Maps to: Emphasizing a **key result** -> Indicate (scene-direction).
    Default: ease_out_back (slight overshoot draws attention).

    Args:
        mobject: The mobject to emphasize.
        run_time: Override duration. Default from ANIMATION_TIMING.indicate.
        rate_func: Override easing. Default ease_out_back.

    Returns:
        An Indicate animation instance.
    """
    _min, _rec, _max = ANIMATION_TIMING.indicate
    rt = run_time or _rec
    rf = rate_func or ease_out_back
    return Indicate(mobject, run_time=rt, rate_func=rf)


def highlight_circle(mobject, *, run_time=None, color=None):
    """Draw an expanding circle around a mobject for focus.

    Maps to: Emphasizing a **key result** -> Circumscribe (scene-direction).

    Args:
        mobject: The mobject to circumscribe.
        run_time: Override duration.
        color: Circle color.

    Returns:
        A Circumscribe animation instance.
    """
    _min, _rec, _max = ANIMATION_TIMING.indicate
    rt = run_time or _rec
    kw = {}
    if color:
        kw["color"] = color
    return Circumscribe(mobject, run_time=rt, **kw)


def transform_step(source, target, *, run_time=None, rate_func=None):
    """Animate an equivalence or transformation between two mobjects.

    Maps to: An **equivalence** or **transformation** -> ReplacementTransform.
    Default: ease_in_out_sine (both endpoints smooth).

    Args:
        source: Source mobject.
        target: Target mobject.
        run_time: Override duration. Default from ANIMATION_TIMING.transform.
        rate_func: Override easing. Default ease_in_out_sine.

    Returns:
        A ReplacementTransform animation instance.
    """
    _min, _rec, _max = ANIMATION_TIMING.transform
    rt = run_time or _rec
    rf = rate_func or ease_in_out_sine
    return ReplacementTransform(source, target, run_time=rt, rate_func=rf)


def shrink_to_corner(mobject, *, corner=DL, scale=0.45, run_time=1.0):
    """Shrink an mobject and move it to a corner for visual persistence.

    Implements the shrink-to-corner pattern from scene-direction SKILL.md
    section 5E. After a formula transforms, keep the old version visible
    at reduced size in a corner so viewers can glance back.

    Args:
        mobject: The mobject to shrink and relocate.
        corner: Target corner (DL, DR, UL, UR). Default DL.
        scale: Scale factor for shrunken version. Default 0.45.
        run_time: Animation duration.

    Returns:
        Tuple of (animation, run_time) for use with self.play().
    """
    anim = mobject.animate.scale(scale).to_corner(corner, buff=BUFFER.MED_LARGE)
    return anim, run_time
