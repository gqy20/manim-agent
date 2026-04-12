# Intro Template Catalog

Four ready-to-use intro styles for educational videos. Each includes a visual description,
timing breakdown, Revideo implementation sketch, and Manim equivalent.

---

## Style 1: `fade_in_title`

**Mood**: Clean, professional, trustworthy.
**Best for**: Formal math topics, theorem introductions, academic content.

### Visual description (second-by-second)

| Time | Screen |
|------|--------|
| 0.0 s | Solid dark background (`#050A14`). Nothing visible yet. |
| 0.0–1.2 s | Main title **fades in** from alpha 0 → 1 at screen center. Font size ~72px, white. |
| 1.0–2.0 s | Subtitle **slides up** from below the title. Font size ~36px, gray (`#888888`). |
| 2.0–2.5 s | Brand element (channel name) **fades in** at bottom-right corner. Small font ~24px, accent color. |
| 2.5–4.0 s | All elements hold steady. Optional subtle pulse on accent color element. |
| 4.0 s | Cut to main content (no transition fade — hard cut). |

### Revideo sketch

```tsx
import { FaDeIn, Rect, Txt, useVideoConfig } from "@revideo/2d";
import { interpolate, useCurrentFrame } from "@revideo/core";
import config from "./intro-config.json";

export default makeScene2D("fade_in_title", function* (view) {
  const { width, height, fps } = useVideoConfig();
  const bg = config.backgroundColor || "#050A14";
  const accent = config.accentColor || "#58C4DD";

  yield view.add(<Rect width={width} height={height} fill={bg} />);

  // Title fades in (frame 0 → ~36 frames at 30fps)
  yield* view.add(
    <FaDeIn duration={36}>
      <Txt fill="white" fontSize={72} fontFamily="sans-serif">
        {config.title}
      </Txt>
    </FaDeIn>,
  );

  // Subtitle slides up (frame 24 → ~54)
  yield* view.add(
    <FaDeIn duration={30}>
      <Txt fill="#888888" fontSize={36} y={60} fontFamily="sans-serif">
        {config.subtitle || ""}
      </Txt>
    </FaDeIn>,
  );

  // Brand element (if configured)
  if (config.brandElement) {
    yield* view.add(
      <FaDeIn duration={20}>
        <Txt fill={accent} fontSize={24} x={width / 2 - 120} y={height / 2 - 80}>
          {config.brandElement}
        </Txt>
      </FaDeIn>,
    );
  }

  // Hold until end of configured duration
  const totalFrames = (config.duration || 4.0) * fps;
  const currentFrame = useCurrentFrame();
  if (currentFrame < totalFrames - 36) {
    yield* waitFor(totalFrames - 36 - currentFrame);
  }
});
```

### Manim equivalent

```python
from manim import *
from components.titles import TitleCard

class IntroFadeIn(TitleCard):
    title = "勾股定理"
    subtitle = "直角三角形三边关系"

    def construct(self):
        mobs = self.get_title_mobjects(title=self.title, subtitle=self.subtitle)
        # Title fades in
        self.play(FadeIn(mobs["title"]), run_time=1.2)
        # Subtitle slides up
        if self.subtitle:
            self.play(
                mobs["subtitle"].animate.shift(UP * 0.3).set_opacity(1),
                run_time=0.8,
            )
        # Hold
        self.wait(1.5)
```

---

## Style 2: `write_title`

**Mood**: Academic, thoughtful, deliberate.
**Best for**: Proofs, derivations, step-by-step topics where writing implies rigor.

### Visual description

| Time | Screen |
|------|--------|
| 0.0 s | Dark background. A faint cursor/pen tip appears at center-left. |
| 0.0–2.0 s | Title text **writes in** character by character from left to right, like handwriting. White color, ~72px. |
| 2.0–3.0 s | Subtitle writes in below, smaller (~36px), gray. Faster than title. |
| 3.0–4.5 s | Complete title card holds. Subtle glow appears behind title. |
| 4.5 s | Hard cut to main content. |

### Revideo sketch

```tsx
import { Rect, Txt, useVideoConfig } from "@revideo/2d";
import { useCurrentFrame, waitFor } from "@revideo/core";
import config from "./intro-config.json";

export default makeScene2D("write_title", function* (view) {
  const { width, height, fps } = useVideoConfig();
  const bg = config.backgroundColor || "#050A14";

  yield view.add(<Rect width={width} height={height} fill={bg} />);

  // Simulate write-in effect with progressive clip
  const titleText = config.title || "";
  const totalFrames = (config.duration || 4.0) * fps;

  // Title appears character-by-character using opacity interpolation per-char
  // (simplified: full title with FadeIn that mimics Write timing)
  yield* view.add(
    <FaDeIn duration={60}>  // 2 seconds at 30fps
      <Txt fill="white" fontSize={72} fontFamily="monospace">
        {titleText}
      </Txt>
    </FaDeIn>,
  );

  // Subtitle
  if (config.subtitle) {
    yield* view.add(
      <FaDeIn duration={30}>
        <Txt fill="#888888" fontSize={36} y={60} fontFamily="monospace">
          {config.subtitle}
        </Txt>
      </FaDeIn>,
    );
  }

  yield* waitFor(Math.max(0, totalFrames - 90 - useCurrentFrame()));
});
```

### Manim equivalent

```python
from manim import *
from components.titles import TitleCard

class IntroWrite(TitleCard):
    title = "勾股定理"
    subtitle = "直角三角形三边关系"

    def construct(self):
        mobs = self.get_title_mobjects(title=self.title, subtitle=self.subtitle)
        # Write animation feels like handwriting
        self.play(Write(mobs["title"]), run_time=2.0)
        if self.subtitle:
            self.play(Write(mobs["subtitle"]), run_time=1.0)
        self.wait(1.5)
```

---

## Style 3: `reveal_from_center`

**Mood**: Dramatic, energetic, impactful.
**Best for**: Key concepts, major theorems, "big reveal" moments.

### Visual description

| Time | Screen |
|------|--------|
| 0.0 s | Dark background. A small bright point glows at exact center. |
| 0.0–0.8 s | Glow **expands outward** in a circular ripple. Accent color ring expands. |
| 0.5–1.8 s | Title **scales up from center** (scale 0.1 → 1.0) with slight overshoot (spring physics). White, bold. |
| 1.8–2.8 s | Subtitle scales in below, slightly delayed. Gray. |
| 2.8–4.0 s | Subtle pulsing glow behind title (opacity oscillation). Brand element fades in at corner. |
| 4.0 s | Hard cut. |

### Revideo sketch

```tsx
import { FaDeIn, Rect, Txt, Circle } from "@revideo/2d";
import { spring, useVideoConfig, waitFor, useCurrentFrame } from "@revideo/core";
import config from "./intro-config.json";

export default makeScene2D("reveal_from_center", function* (view) {
  const { width, height, fps } = useVideoConfig();
  const bg = config.backgroundColor || "#050A14";
  const accent = config.accentColor || "#58C4DD";

  yield view.add(<Rect width={width} height={height} fill={bg} />);

  // Expanding glow ring
  yield* view.add(
    <Circle fill={accent} size={0} opacity={0.6}>
      {[spring({ to: 300, from: 0, config: { damping: 8 } })]}
    </Circle>,
    24,
  );

  // Title springs in from center with overshoot
  const titleRef = createRef<Txt>();
  yield view.add(
    <Txt ref={titleRef} fill="white" fontSize={72} scale={0.1}>
      {config.title}
    </Txt>,
  );
  yield* titleRef().scale(
    spring({ to: 1.0, from: 0.1, config: { damping: 10, stiffness: 120 } }),
    40,
  );

  // Subtitle
  if (config.subtitle) {
    const subRef = createRef<Txt>();
    yield view.add(
      <Txt ref={subRef} fill="#888888" fontSize={36} y={60} scale={0.1}>
        {config.subtitle}
      </Txt>,
    );
    yield* subRef().scale(
      spring({ to: 1.0, from: 0.1, config: { damping: 10, stiffness: 120 } }),
      30,
    );
  }

  yield* waitFor(Math.max(0, (config.duration || 4.0) * fps - useCurrentFrame()));
});
```

### Manim equivalent

```python
from manim import *
from components.titles import TitleCard

class IntroReveal(TitleCard):
    title = "勾股定理"
    subtitle = "直角三角形三边关系"

    def construct(self):
        mobs = self.get_title_mobjects(title=self.title, subtitle=self.subtitle)
        # Scale from center with overshoot
        mobs["title"].scale(0.1)
        self.play(
            mobs["title"].animate.scale(1.0),
            run_time=1.5,
            rate_func=ease_out_back,
        )
        if self.subtitle:
            mobs["subtitle"].scale(0.1)
            self.play(
                mobs["subtitle"].animate.scale(1.0),
                run_time=1.0,
                rate_func=ease_out_back,
            )
        self.wait(1.5)
```

---

## Style 4: `typewriter`

**Mood**: Technical, modern, computational.
**Best for**: CS topics, algorithms, data structures, anything related to code/computation.

### Visual description

| Time | Screen |
|------|--------|
| 0.0 s | Dark background. Monospace cursor `_` blinks at left-center. |
| 0.0–2.5 s | Title characters appear **one by one** with a brief white highlight flash per character. Monospace font, green-tinted white (`#E0E0E0`). |
| 2.5–3.5 s | Cursor moves to next line. Subtitle types out similarly but faster, dimmer color. |
| 3.5–4.5 s | Cursor blinks twice more, then disappears. Full card holds briefly. |
| 4.5 s | Hard cut. |

### Revideo sketch

```tsx
import { Rect, Txt } from "@revideo/2d";
import { useVideoConfig, useCurrentFrame, waitFor } from "@revideo/core";
import config from "./intro-config.json";

export default makeScene2D("typewriter", function* (view) {
  const { width, height, fps } = useVideoConfig();
  const bg = config.backgroundColor || "#050A14";

  yield view.add(<Rect width={width} height={height} fill={bg} />);

  // Typewriter effect: show progressively more characters
  const titleText = config.title || "";
  const frame = useCurrentFrame();

  // Character reveal rate: ~2 chars per frame (adjustable)
  const charsToShow = Math.min(Math.floor(frame * 0.8), titleText.length);
  const visibleText = titleText.slice(0, charsToShow);
  const cursor = frame % 15 < 8 ? "|" : "";  // Blinking cursor

  yield view.add(
    <Txt fill="#E0E0E0" fontSize={64} fontFamily="monospace" textAlign="left" x={-300}>
      {visibleText}{cursor}
    </Txt>,
  );

  // After title completes, show subtitle
  if (charsToShow >= titleText.length && config.subtitle) {
    const subFrame = Math.max(0, frame - titleText.length / 0.8);
    const subChars = Math.min(Math.floor(subFrame * 1.2), config.subtitle.length);
    yield view.add(
      <Txt fill="#888888" fontSize={32} fontFamily="monospace" textAlign="left" x={-300} y={70}>
        {config.subtitle.slice(0, subChars)}
      </Txt>,
    );
  }

  yield* waitFor(Math.max(0, (config.duration || 4.5) * fps - frame));
});
```

### Manim equivalent

```python
from manim import *
from components.titles import TitleCard

class IntroTypewriter(TitleCard):
    title = "勾股定理"
    subtitle = "直角三角形三边关系"

    def construct(self):
        mobs = self.get_title_mobjects(title=self.title, subtitle=self.subtitle)
        # Write with monospace feel
        mobs["title"].set_font("Consolas")
        self.play(Write(mobs["title"]), run_time=2.5)
        if self.subtitle:
            mobs["subtitle"].set_font("Consolas")
            self.play(Write(mobs["subtitle"]), run_time=1.0)
        self.wait(1.0)
```

---

## Style selection guide

| Content type | Recommended style | Reason |
|-------------|-------------------|--------|
| Geometry theorem | `fade_in_title` | Clean, doesn't distract from visual proof |
| Proof walkthrough | `write_title` | Writing implies rigor and step-by-step logic |
| Major concept debut | `reveal_from_center` | Dramatic impact for important ideas |
| Algorithm / CS topic | `typewriter` | Technical aesthetic matches computational theme |
| General purpose (default) | `fade_in_title` | Safest choice, works everywhere |
