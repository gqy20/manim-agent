# Manim Fallback Guide

When Revideo is not available, generate intro/outro segments as standalone Manim scenes
using the existing `TitleCard` and `EndingCard` components.

## When to use this fallback

- Revideo / Node.js is not installed on the system.
- The user explicitly requests `--intro-outro-backend manim`.
- Revideo rendering fails and automatic fallback is triggered.
- Quick iteration phase where Manim's faster edit-render cycle is preferred.

## Component API reference

### TitleCard (for intros)

Located at `components/titles.py`.

**Factory method** (preferred for embedded use):
```python
mobs = TitleCard.get_title_mobjects(
    title="勾股定理",
    subtitle="直角三角形三边关系",
    title_color=None,     # None = COLOR_PALETTE.neutral
    subtitle_color=None,  # None = COLOR_PALETTE.de_emphasized
)
# Returns: {"title": Mobject, "subtitle": Mobject (optional)}
```

**Standalone Scene subclass**:
```python
class MyIntro(TitleCard):
    title = "标题文字"
    subtitle = "副标题文字"
    # Override construct() for custom animation
```

### EndingCard (for outros)

Located at `components/titles.py`.

**Factory method**:
```python
mobs = EndingCard.get_ending_mobjects(
    message="结论文字",
    show_qed=False,
    message_color=None,  # None = COLOR_PALETTE.conclusion
)
# Returns: {"message": Mobject, "qed": Mobject (optional)}
```

**Standalone Scene subclass**:
```python
class MyOutro(EndingCard):
    message = "结论文字"
    show_qed = True
    # Override construct() for custom animation
```

## File placement convention

Place fallback scene files in the task directory:

```
{task_dir}/
├── scene.py                  # Main content scene (existing)
├── intro_scene.py            # Standalone intro scene (NEW)
└── outro_scene.py            # Standalone outro scene (NEW)
```

## Complete intro scene templates

### Template A: fade_in_title (default)

```python
"""Intro scene: fade_in_title style — clean professional opening."""
from manim import *

from components.titles import TitleCard


class IntroScene(TitleCard):
    """Standard fade-in title card intro."""

    title = ""       # Set dynamically
    subtitle = ""    # Set dynamically

    def construct(self) -> None:
        mobs = self.get_title_mobjects(
            title=self.title,
            subtitle=self.subtitle,
        )
        # Phase 1: Title fades in (0-1.2s)
        self.play(FadeIn(mobs["title"]), run_time=1.2, rate_func=ease_out_cubic)
        # Phase 2: Subtitle slides up (1.0-2.0s)
        if self.subtitle:
            mobs["subtitle"].shift(DOWN * 0.3).set_opacity(0)
            self.play(
                mobs["subtitle"].animate.shift(UP * 0.0).set_opacity(1),
                run_time=0.8,
                rate_func=ease_out_cubic,
            )
        # Phase 3: Hold (2.0-4.0s)
        self.wait(2.0)
```

### Template B: write_title (academic)

```python
"""Intro scene: write_title style — handwritten feel."""
from manim import *

from components.titles import TitleCard


class IntroScene(TitleCard):
    """Write-in title card intro for academic content."""

    title = ""
    subtitle = ""

    def construct(self) -> None:
        mobs = self.get_title_mobjects(
            title=self.title,
            subtitle=self.subtitle,
        )
        # Title writes in character by character (0-2.0s)
        self.play(Write(mobs["title"]), run_time=2.0, rate_func=linear)
        # Subtitle writes faster (2.0-3.0s)
        if self.subtitle:
            self.play(Write(mobs["subtitle"]), run_time=1.0, rate_func=linear)
        # Hold (3.0-4.5s)
        self.wait(1.5)
```

### Template C: reveal_from_center (dramatic)

```python
"""Intro scene: reveal_from_center style — dramatic scale-up."""
from manim import *

from components.titles import TitleCard


class IntroScene(TitleCard):
    """Scale-from-center dramatic intro."""

    title = ""
    subtitle = ""

    def construct(self) -> None:
        mobs = self.get_title_mobjects(
            title=self.title,
            subtitle=self.subtitle,
        )
        # Start tiny at center
        mobs["title"].scale(0.1)
        # Scale up with overshoot (0.5-1.8s)
        self.play(
            mobs["title"].animate.scale(1.0),
            run_time=1.3,
            rate_func=ease_out_back,
        )
        # Subtitle follows (1.8-2.8s)
        if self.subtitle:
            mobs["subtitle"].scale(0.1)
            self.play(
                mobs["subtitle"].animate.scale(1.0),
                run_time=1.0,
                rate_func=ease_out_back,
            )
        # Hold (2.8-4.5s)
        self.wait(1.7)
```

### Template D: typewriter (technical)

```python
"""Intro scene: typewriter style — monospace character-by-character."""
from manim import *

from components.titles import TitleCard


class IntroScene(TitleCard):
    """Typewriter-style intro for CS/technical content."""

    title = ""
    subtitle = ""

    def construct(self) -> None:
        mobs = self.get_title_mobjects(
            title=self.title,
            subtitle=self.subtitle,
        )
        # Set monospace font for typewriter feel
        mobs["title"].set_font("Consolas")
        # Write with slower pace for typewriter effect (0-2.5s)
        self.play(Write(mobs["title"]), run_time=2.5, rate_func=linear)
        if self.subtitle:
            mobs["subtitle"].set_font("Consolas")
            self.play(Write(mobs["subtitle"]), run_time=1.0, rate_func=linear)
        # Hold (3.5-4.5s)
        self.wait(1.0)
```

## Complete outro scene templates

### Template A: takeaway_card (default)

```python
"""Outro scene: takeaway_card style — highlighted conclusion box."""
from manim import *

from components.config import COLOR_PALETTE, BUFFER
from components.titles import EndingCard


class OutroScene(EndingCard):
    """Takeaway card outro with highlighted border."""

    message = ""

    def construct(self) -> None:
        mobs = self.get_ending_mobjects(message=self.message)
        # Draw border around message
        border = SurroundingRectangle(
            mobs["message"],
            color=COLOR_PALETTE.conclusion,
            buff=BUFFER.MED_LARGE,
            corner_radius=0.12,
        )
        # Phase 1: Draw border (0-1.0s)
        self.play(Create(border), run_time=1.0)
        # Phase 2: Fade in message (0.8-2.0s)
        self.play(FadeIn(mobs["message"]), run_time=1.2, rate_func=ease_out_cubic)
        # Phase 3: Subtle glow pulse (2.0-3.5s)
        self.play(border.animate.set_opacity(0.6), run_time=0.5)
        self.play(border.animate.set_opacity(0.3), run_time=0.5)
        # Phase 4: Hold (3.5-4.0s)
        self.wait(0.5)
        # Phase 5: Fade out (4.0-4.8s)
        self.play(
            FadeOut(mobs["message"]),
            FadeOut(border),
            run_time=0.8,
            rate_func=ease_in_cubic,
        )
```

### Template B: cta_banner (social)

```python
"""Outro scene: cta_banner style — call-to-action with subscribe reminder."""
from manim import *

from components.config import COLOR_PALETTE
from components.titles import EndingCard


class OutroScene(EndingCard):
    """CTA banner outro with subscribe reminder."""

    message = ""
    cta_text = "点赞关注，下期见"
    subscribe_reminder = False

    def construct(self) -> None:
        mobs = self.get_ending_mobjects(message=self.message)
        # Move message to upper area
        mobs["message"].to_edge(UP, buff=MED_LARGE_BUFF)
        # Phase 1: Fade in takeaway message (0-1.5s)
        self.play(FadeIn(mobs["message"]), run_time=1.5)
        # Build CTA banner
        banner = Rectangle(
            height=0.8,
            width=config.frame_width,
            fill_color="#111122",
            fill_opacity=1,
            stroke_color=COLOR_PALETTE.conclusion,
            stroke_width=2,
        )
        banner.next_to(mobs["message"], DOWN, buff=LARGE_BUFF)
        banner.shift(DOWN * 1.2)  # Start off-screen bottom
        cta = Text(self.cta_text, font_size=28, color=COLOR_PALETTE.conclusion)
        cta.move_to(banner.get_center())
        group = VGroup(banner, cta)
        # Phase 2: Banner slides up (1.5-2.5s)
        self.play(group.animate.shift(UP * 1.2), run_time=1.0, rate_func=ease_out_cubic)
        # Phase 3: Hold (2.5-4.0s)
        self.wait(1.5)
        # Phase 4: Fade all out (4.0-5.0s)
        self.play(
            FadeOut(mobs["message"]),
            FadeOut(group),
            run_time=1.0,
            rate_func=ease_in_cubic,
        )
```

### Template C: minimal_fade (calm)

```python
"""Outro scene: minimal_fade style — calm reflective ending."""
from manim import *

from components.titles import EndingCard


class OutroScene(EndingCard):
    """Minimal fade outro for reflective endings."""

    message = ""

    def construct(self) -> None:
        mobs = self.get_ending_mobjects(message=self.message)
        mobs["message"].set_color("#DDDDE0")
        # Phase 1: Very slow gentle fade in (0.5-1.5s)
        self.play(
            FadeIn(mobs["message"]),
            run_time=1.5,
            rate_func=ease_in_cubic,
        )
        # Phase 2: Long hold — completely still (1.5-3.5s)
        self.wait(2.0)
        # Phase 3: Gentle fade out (3.5-4.5s)
        self.play(
            FadeOut(mobs["message"]),
            run_time=1.0,
            rate_func=ease_out_cubic,
        )
```

### Template D: qed_style (formal proof)

```python
"""Outro scene: qed_style style — formal proof ending with Q.E.D. mark."""
from manim import *

from components.config import COLOR_PALETTE
from components.titles import EndingCard


class OutroScene(EndingCard):
    """Q.E.D.-style outro for proof conclusions."""

    message = ""
    show_qed = True

    def construct(self) -> None:
        mobs = self.get_ending_mobjects(
            message=self.message,
            show_qed=self.show_qed,
        )
        # Phase 1: Q.E.D. mark draws in (0-1.2s)
        if self.show_qed:
            self.play(Write(mobs["qed"]), run_time=1.2)
            self.wait(0.3)
        # Phase 2: Takeaway message (1.0-2.2s)
        self.play(FadeIn(mobs["message"]), run_time=1.2, rate_func=ease_out_cubic)
        # Phase 3: Pulse Q.E.D. once (2.2-2.8s)
        if self.show_qed:
            self.play(
                mobs["qed"].animate.scale(1.15),
                run_time=0.3,
                rate_func=ease_out_back,
            )
            self.play(
                mobs["qed"].animate.scale(1.0),
                run_time=0.3,
            )
        # Phase 4: Hold (2.8-3.8s)
        self.wait(1.0)
        # Phase 5: Coordinated fade out (3.8-4.6s)
        fade_group = [mobs["message"]]
        if self.show_qed:
            fade_group.append(mobs["qed"])
        self.play(*[FadeOut(m) for m in fade_group], run_time=0.8)
```

## Rendering workflow

### Step-by-step commands

```bash
# 1. Navigate to task directory
cd {task_dir}

# 2. Render intro scene
manim -qh intro_scene.py IntroScene
# Output: media/videos/intro_scene.mp4 (1080p30)

# 3. Render outro scene
manim -qh outro_scene.py OutroScene
# Output: media/videos/outro_scene.mp4 (1080p30)

# 4. Verify durations
ffprobe -v quiet -print_format json -show_format media/videos/intro_scene.mp4 | grep duration
ffprobe -v quiet -print_format json -show_format media/videos/outro_scene.mp4 | grep duration

# 5. Copy to expected locations (pipeline will look here)
cp media/videos/intro_scene.mp4 ./intro.mp4
cp media/videos/outro_scene.mp4 ./outro.mp4
```

### Duration control checklist

To ensure 3–5 second output:

- [ ] Each `self.play()` call has explicit `run_time` (no implicit defaults).
- [ ] Total of all `run_time` + `wait()` = target duration ± 0.2s.
- [ ] No single animation exceeds 2.5 seconds.
- [ ] Total `self.wait()` ≤ 1.5 seconds.
- [ ] Verify with ffprobe after rendering.
- [ ] If too long: reduce hold times first, then animation durations.
- [ ] If too short: increase hold time (cheapest way to pad).

### Resolution notes

Manim `-qh` flag produces:
- **Resolution**: 1920 × 1080 pixels
- **FPS**: 30 frames per second
- **Codec**: H.264 (libx264)
- **Container**: MP4

This matches the Revideo output spec exactly. No conversion needed before concatenation.
