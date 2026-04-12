"""Standard title cards and ending frames for teaching animations.

Provides:
  - TitleCard: Configurable opening title with optional subtitle
  - EndingCard: Standard conclusion / takeaway frame

Design pattern adapted from 3b1b's custom/opening_quote.py and custom/banner.py:
  - Class-attribute configuration for easy subclass customization
  - get_* factory methods separating creation from orchestration
  - Template Method pattern via construct() hook
"""
from __future__ import annotations

from manim import (
    DOWN,
    FadeIn,
    MathTex,
    ORIGIN,
    Scene,
    UP,
    VGroup,
    Write,
    YELLOW,
)
from manim.mobject.frame import FullScreenRectangle

from .config import BUFFER, COLOR_PALETTE, TEXT_SIZES
from .text_helpers import cjk_title, cjk_text, subtitle


class TitleCard(Scene):
    """Standard opening title card for educational videos.

    Displays a centered title with optional subtitle line below it.
    Designed to occupy the first 2-3 seconds of any teaching scene.

    Class attributes (override in subclass):
        title: Main title text (required).
        subtitle: Optional secondary line below title.
        show_background: Whether to draw a subtle full-screen border.

    Usage in a scene:
        # Option A: As a standalone scene (for video assembly)
        class MyTitle(TitleCard):
            title = "勾股定理"
            subtitle = "直角三角形三边关系"

        # Option B: Extract mobjects for embedding in a larger scene
        title_mobjects = TitleCard.get_title_mobjects(
            title="勾股定理",
            subtitle="直角三角形三边关系",
        )
    """

    title: str = ""
    subtitle: str = ""
    title_color = COLOR_PALETTE.neutral
    subtitle_color = COLOR_PALETTE.de_emphasized
    show_background: bool = False

    def construct(self) -> None:
        mobs = self.get_title_mobjects(
            title=self.title,
            subtitle=self.subtitle,
            title_color=self.title_color,
            subtitle_color=self.subtitle_color,
        )
        if self.show_background:
            self.add(FullScreenRectangle())
        self.play(Write(mobs["title"]), run_time=1.5)
        if self.subtitle:
            self.play(FadeIn(mobs["subtitle"]), run_time=0.8)
        self.wait(0.5)

    @staticmethod
    def get_title_mobjects(
        title: str,
        subtitle_text: str = "",
        *,
        title_color=None,
        subtitle_color=None,
    ) -> dict[str, object]:
        """Factory method: create title mobjects without animating them.

        Returns a dict with keys 'title' and optionally 'subtitle'.
        Caller positions and animates them as needed.

        Args:
            title: Main title text.
            subtitle_text: Optional secondary line.
            title_color: Override color for title.
            subtitle_color: Override color for subtitle.

        Returns:
            Dict of mobjects ready for positioning.
        """
        title_mob = cjk_title(title, color=title_color)
        title_mob.to_edge(UP, buff=BUFFER.MED_LARGE)
        result: dict[str, object] = {"title": title_mob}
        if subtitle_text:
            sub_mob = subtitle(subtitle_text, color=subtitle_color)
            sub_mob.next_to(title_mob, DOWN, buff=BUFFER.SMALL)
            result["subtitle"] = sub_mob
        return result


class EndingCard(Scene):
    """Standard conclusion frame for educational videos.

    Shows a takeaway message, optionally with a Q.E.D.-style mark
    or a summary formula. Designed to feel like a natural payoff.

    Class attributes:
        message: Conclusion / takeaway text.
        show_qed: Whether to display a Q.E.D. mark.
        message_color: Color for the conclusion text.
    """

    message: str = ""
    show_qed: bool = False
    message_color = COLOR_PALETTE.conclusion

    def construct(self) -> None:
        mobs = self.get_ending_mobjects(
            message=self.message,
            show_qed=self.show_qed,
            message_color=self.message_color,
        )
        if self.show_qed:
            self.play(Write(mobs["qed"]), run_time=1.0)
            self.wait(0.3)
        self.play(FadeIn(mobs["message"]), run_time=1.0)
        self.wait(1.0)

    @staticmethod
    def get_ending_mobjects(
        message: str,
        *,
        show_qed: bool = False,
        message_color=None,
    ) -> dict[str, object]:
        """Factory method: create ending mobjects without animating.

        Args:
            message: Takeaway / conclusion text.
            show_qed: Include a Q.E.D. mark.
            message_color: Override color for message.

        Returns:
            Dict with 'message' key and optionally 'qed' key.
        """
        result: dict[str, object] = {}
        if show_qed:
            qed = MathTex(r"\\text{Q.E.D.}", color=YELLOW)
            qed.scale(TEXT_SIZES.label)
            qed.to_edge(DOWN + LEFT, buff=BUFFER.LARGE)
            result["qed"] = qed
        msg = cjk_text(message, color=message_color)
        msg.move_to(ORIGIN)
        result["message"] = msg
        return result
