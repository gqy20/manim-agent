"""Base scene template for educational teaching animations.

Provides:
  - TeachingScene: Pre-configured Scene with convenience methods

Design patterns adapted from 3b1b:
  - Class-attribute configuration (title, mode, etc.)
  - Template Method: setup() -> construct() with overridable hooks
  - get_* factory methods for creating scene-specific mobjects

The LLM should subclass TeachingScene for most generated scenes:
    class PythagoreanScene(TeachingScene):
        title = "勾股定理"
        mode = SceneMode.GEOMETRY_CONSTRUCTION

        def construct(self):
            self.show_figure()
            self.annotate_vertices()
            self.show_derivation()
            self.conclude()
"""
from __future__ import annotations

from manim import Scene

from .config import ANIMATION_TIMING
from .layouts import SceneMode
from .titles import TitleCard


class TeachingScene(Scene):
    """Base scene class for educational Manim animations.

    Class attributes (override in subclass):
        title: Scene title displayed in the title zone.
        mode: SceneMode enum determining layout template.
        target_duration: Approximate target duration in seconds (informational).

    Convenience methods:
        beat_pause(): Insert a standard inter-beat pause.
        conclude(): Show ending frame with standard pause.
    """

    title: str = ""
    mode: SceneMode = SceneMode.CONCEPT_EXPLAINER
    target_duration: float = 30.0  # seconds

    def setup(self) -> None:
        """Called before construct(). Override to add persistent elements.

        Default implementation adds the title if configured.
        """
        super().setup()
        if self.title:
            title_mobs = TitleCard.get_title_mobjects(self.title)
            self.add(title_mobs["title"])
            if "subtitle" in title_mobs:
                self.add(title_mobs["subtitle"])

    def beat_pause(self, duration: float | None = None) -> None:
        """Insert a standard pause between beats.

        Args:
            duration: Pause length in seconds. Default mid-range from
                       ANIMATION_TIMING.wait (0.55s).
        """
        _min, _rec, _max = ANIMATION_TIMING.wait
        self.wait(duration if duration is not None else _rec)

    def conclude(self, message: str = "", wait_after: float = 1.0) -> None:
        """Show the conclusion frame with optional message and final pause.

        Args:
            message: Optional takeaway text to display.
            wait_after: Seconds of final pause before scene ends.
        """
        if message:
            from .titles import EndingCard

            mobs = EndingCard.get_ending_mobjects(message)
            self.add(mobs["message"])
        self.wait(wait_after)
