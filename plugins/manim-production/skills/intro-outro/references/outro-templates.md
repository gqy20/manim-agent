# Outro Template Catalog

Four ready-to-use outro styles for educational videos. Each includes a visual description,
timing breakdown, Revideo implementation sketch, and Manim equivalent.

---

## Style 1: `takeaway_card`

**Mood**: Conclusive, satisfying, clean.
**Best for**: Proof endings, key results, formula takeaways.

### Visual description (second-by-second)

| Time | Screen |
|------|--------|
| 0.0 s | Dark background (`#050A14`). Faint border rectangle draws at center (thin line, accent color). |
| 0.0–1.0 s | Border rectangle **draws in** (stroke animation). Size ~60% of screen. |
| 0.8–2.0 s | Takeaway message **fades in** inside the border. Centered, white, ~48px. Key formula/expression in accent color. |
| 2.0–3.5 s | Message holds. Border emits **subtle glow pulse** (opacity oscillation 0.4→0.8→0.4). |
| 3.5–4.5 s | Entire card **fades out gently** to black. |
| 4.5 s | End. |

### Revideo sketch

```tsx
import { FaDeIn, FaDeOut, Rect, Txt } from "@revideo/2d";
import { useVideoConfig, waitFor, useCurrentFrame, loop } from "@revideo/core";
import config from "./outro-config.json";

export default makeScene2D("takeaway_card", function* (view) {
  const { width, height, fps } = useVideoConfig();
  const bg = config.backgroundColor || "#050A14";
  const accent = config.accentColor || "#83C167";

  yield view.add(<Rect width={width} height={height} fill={bg} />);

  // Draw border rectangle
  yield* view.add(
    <Rect
      width={width * 0.6}
      height={height * 0.35}
      stroke={accent}
      strokeWidth={2}
      fill="none"
      radius={12}
    />,
    30,
  );

  // Message fades in
  yield* view.add(
    <FaDeIn duration={36}>
      <Txt fill="white" fontSize={48} textAlign="center">
        {config.message || ""}
      </Txt>
    </FaDeIn>,
  );

  // Hold with glow
  yield* waitFor(Math.max(0, (config.duration || 4.0) * fps - 66 - useCurrentFrame()));

  // Fade out
  yield* view.add(
    <FaDeOut duration={20}>
      <Rect
        width={width * 0.6}
        height={height * 0.35}
        fill={bg}
        radius={12}
      />
    </FaDeOut>,
  );
});
```

### Manim equivalent

```python
from manim import *
from components.titles import EndingCard

class OutroTakeaway(EndingCard):
    message = "记住：a² + b² = c²"

    def construct(self):
        mobs = self.get_ending_mobjects(message=self.message)
        # Draw border
        border = SurroundingRectangle(
            mobs["message"],
            color=COLOR_PALETTE.conclusion,
            buff=MED_LARGE_BUFF,
            corner_radius=0.12,
        )
        self.play(Create(border), run_time=1.0)
        self.play(FadeIn(mobs["message"]), run_time=1.2)
        # Subtle glow
        self.play(border.animate.set_opacity(0.6), run_time=0.5)
        self.play(border.animate.set_opacity(0.3), run_time=0.5)
        # Hold then fade
        self.wait(1.0)
        self.play(
            FadeOut(mobs["message"]),
            FadeOut(border),
            run_time=0.8,
        )
```

---

## Style 2: `cta_banner`

**Mood**: Engaging, social, action-oriented.
**Best for**: Channel growth focus, series content, encouraging subscriptions.

### Visual description

| Time | Screen |
|------|--------|
| 0.0 s | Dark background. Takeaway message centered, faded in softly (smaller ~36px). |
| 0.0–1.5 s | Message fades in at upper-center area. |
| 1.5–2.5 s | Bottom **banner slides up** from off-screen bottom edge. Banner has CTA text ("点赞关注") + subscribe icon area. Accent-colored left border on banner. |
| 2.5–4.0 s | Both hold. Banner pulses subtly. Optional animated subscribe icon (checkmark or bell). |
| 4.0–5.0 s | Everything fades out together. |

### Revideo sketch

```tsx
import { FaDeIn, FaDeOut, Rect, Txt } from "@revideo/2d";
import { useVideoConfig, waitFor, useCurrentFrame } from "@revideo/core";
import config from "./outro-config.json";

export default makeScene2D("cta_banner", function* (view) {
  const { width, height, fps } = useVideoConfig();
  const bg = config.backgroundColor || "#050A14";
  const accent = config.accentColor || "#83C167";

  yield view.add(<Rect width={width} height={height} fill={bg} />);

  // Takeaway message at top
  yield* view.add(
    <FaDeIn duration={30}>
      <Txt fill="white" fontSize={40} y={-100}>
        {config.message || ""}
      </Txt>
    </FaDeIn>,
  );

  // CTA banner slides up from bottom
  const bannerHeight = 100;
  yield* view.add(
    <Rect
      width={width}
      height={bannerHeight}
      fill="#111122"
      y={height / 2 - bannerHeight / 2 + 400}  // Starts off-screen
    >
      {[{ y: height / 2 - bannerHeight / 2 }]}  // Slide to bottom
    </Rect>,
    30,
  );

  // CTA text on banner
  yield* view.add(
    <FaDeIn duration={20}>
      <Txt fill={accent} fontSize={32} y={height / 2 - bannerHeight / 2 + 10}>
        {config.ctaText || "点赞关注，下期见"}
      </Txt>
    </FaDeIn>,
  );

  // Subscribe reminder icon/text
  if (config.subscribeReminder) {
    yield* view.add(
      <FaDeIn duration={20}>
        <Txt fill="#AAAAAA" fontSize={24} y={height / 2 - bannerHeight / 2 + 10} x={200}>
          🔔 订阅获取更多内容
        </Txt>
      </FaDeIn>,
    );
  }

  yield* waitFor(Math.max(0, (config.duration || 5.0) * fps - useCurrentFrame()));
});
```

### Manim equivalent

```python
from manim import *
from components.titles import EndingCard

class OutroCTABanner(EndingCard):
    message = "记住：a² + b² = c²"

    def construct(self):
        mobs = self.get_ending_mobjects(message=self.message)
        # Message at top
        mobs["message"].shift(UP * 2)
        self.play(FadeIn(mobs["message"]), run_time=1.2)

        # CTA banner at bottom
        banner = Rectangle(height=0.8, width=config.frame_width, fill_color="#111122", fill_opacity=1)
        banner.to_edge(DOWN, buff=0)
        banner.shift(DOWN * 1.0)  # Start off-screen
        cta_text = Text("点赞关注，下期见", font_size=28, color=COLOR_PALETTE.conclusion)
        cta_text.move_to(banner.get_center())

        self.play(banner.animate.to_edge(DOWN, buff=0), FadeIn(cta_text), run_time=1.0)
        self.wait(2.0)
        self.play(
            FadeOut(mobs["message"]),
            FadeOut(banner),
            FadeOut(cta_text),
            run_time=0.8,
        )
```

---

## Style 3: `minimal_fade`

**Mood**: Calm, reflective, elegant.
**Best for**: Summary takeaways, contemplative endings, minimalist channels.

### Visual description

| Time | Screen |
|------|--------|
| 0.0 s | Pure dark background. Nothing visible. |
| 0.5–1.5 s | Takeaway message **fades in very slowly** (gentle ease-in). Centered, medium size (~44px), slightly warm white. |
| 1.5–3.5 s | Message holds perfectly still. No animations, no movement. Let the viewer read and absorb. |
| 3.5–4.5 s | Message **fades out slowly** (symmetric ease-out). Back to pure dark. |
| 4.5 s | End. |

### Revideo sketch

```tsx
import { FaDeIn, FaDeOut, Rect, Txt } from "@revideo/2d";
import { useVideoConfig, waitFor, useCurrentFrame } from "@revideo/core";
import config from "./outro-config.json";

export default makeScene2D("minimal_fade", function* (view) {
  const { width, height, fps } = useVideoConfig();
  const bg = config.backgroundColor || "#050A14";

  yield view.add(<Rect width={width} height={height} fill={bg} />);

  // Slow fade in
  yield* view.add(
    <FaDeIn duration={45}>
      <Txt fill="#DDDDE0" fontSize={44} fontFamily="serif" textAlign="center">
        {config.message || ""}
      </Txt>
    </FaDeIn>,
  );

  // Long hold — let viewer absorb
  yield* waitFor(Math.max(0, (config.duration || 4.5) * fps - 45 - 30 - useCurrentFrame()));

  // Slow fade out
  yield* view.add(
    <FaDeOut duration={30}>
      <Txt fill="#DDDDE0" fontSize={44}>
        {config.message || ""}
      </Txt>
    </FaDeIn>,
  );
});
```

### Manim equivalent

```python
from manim import *
from components.titles import EndingCard

class OutroMinimal(EndingCard):
    message = "记住：a² + b² = c²"

    def construct(self):
        mobs = self.get_ending_mobjects(message=self.message)
        mobs["message"].set_color("#DDDDE0")
        # Very slow, gentle fade in
        self.play(FadeIn(mobs["message"]), run_time=1.5, rate_func=ease_in_cubic)
        # Long hold — no movement
        self.wait(2.0)
        # Gentle fade out
        self.play(FadeOut(mobs["message"]), run_time=1.0, rate_func=ease_out_cubic)
```

---

## Style 4: `qed_style`

**Mood**: Formal, academic, conclusive.
**Best for**: Proof walkthroughs, mathematical derivations, Q.E.D. moments.

### Visual description

| Time | Screen |
|------|--------|
| 0.0 s | Dark background. Small square appears at lower-right area. |
| 0.0–1.2 s | **Q.E.D. mark** (□ or ∎) **draws in** with a bright accent-color stroke. Slight glow on completion. |
| 1.0–2.2 s | Takeaway message **writes/fades in** near center. White, ~44px. If there's a key formula, it appears in accent color below. |
| 2.2–3.5 s | Both hold. Q.E.D. mark pulses once softly. |
| 3.5–4.5 s | Gentle coordinated fade-out of all elements. |
| 4.5 s | End. |

### Revideo sketch

```tsx
import { FaDeIn, FaDeOut, Rect, Txt, Circle } from "@revideo/2d";
import { useVideoConfig, waitFor, useCurrentFrame, spring } from "@revideo/core";
import config from "./outro-config.json";

export default makeScene2D("qed_style", function* (view) {
  const { width, height, fps } = useVideoConfig();
  const bg = config.backgroundColor || "#050A14";
  const accent = config.accentColor || "#83C167";

  yield view.add(<Rect width={width} height={height} fill={bg} />);

  // Q.E.D. mark draws in at lower right
  const qedRef = createRef<Rect>();
  yield view.add(
    <Rect
      ref={qedRef}
      width={40}
      height={40}
      stroke={accent}
      strokeWidth={3}
      fill="none"
      x={width / 2 - 150}
      y={height / 2 - 100}
    />,
  );
  // Animate stroke drawing (simulate with scale + fade)
  yield* qedRef().fade(0, 1, 36);
  yield* qedRef().scale(spring({ to: 1.2, from: 1.0, config: { damping: 8 } }), 12);
  yield* qedRef().scale(spring({ to: 1.0, from: 1.2, config: { damping: 8 } }), 12);

  // Takeaway message
  yield* view.add(
    <FaDeIn duration={36}>
      <Txt fill="white" fontSize={44} y={30}>
        {config.message || ""}
      </Txt>
    </FaDeIn>,
  );

  // Hold
  yield* waitFor(Math.max(0, (config.duration || 4.5) * fps - 36 - 36 - useCurrentFrame()));

  // Coordinated fade out
  yield* view.add(<FaDeOut duration={24}><Rect width={width} height={height} fill={bg} /></FaDeOut>,);
});
```

### Manim equivalent

```python
from manim import *
from components.titles import EndingCard

class OutroQED(EndingCard):
    message = "证明完毕：a² + b² = c²"
    show_qed = True

    def construct(self):
        mobs = self.get_ending_mobjects(message=self.message, show_qed=True)
        # Q.E.D. mark first
        if self.show_qed:
            self.play(Write(mobs["qed"]), run_time=1.2)
            self.wait(0.3)
        # Then takeaway message
        self.play(FadeIn(mobs["message"]), run_time=1.2)
        # Pulse QED
        self.play(
            mobs["qed"].animate.scale(1.15),
            run_time=0.3,
            rate_func=ease_out_back,
        )
        self.play(
            mobs["qed"].animate.scale(1.0),
            run_time=0.3,
        )
        self.wait(1.0)
        # Coordinated fade out
        self.play(
            FadeOut(mobs["message"]),
            *[FadeOut(m) for m in [mobs["qed"]] if self.show_qed],
            run_time=0.8,
        )
```

---

## Style selection guide

| Content type | Recommended style | Reason |
|-------------|-------------------|--------|
| Proof ending | `qed_style` | Formal Q.E.D. matches proof context |
| Key result / formula | `takeaway_card` | Highlighted box draws attention to result |
| Series episode end | `cta_banner` | Encourages subscription and return viewers |
| Reflective summary | `minimal_fade` | Calm, lets the math sink in |
| General purpose (default) | `takeaway_card` | Works well for most educational content |
