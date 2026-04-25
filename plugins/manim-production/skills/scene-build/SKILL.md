---
name: scene-build
description: Build a Manim scene from an existing scene plan. Use when a beat-by-beat plan already exists and the next step is to implement, render, and refine the animation code. Trigger for requests like "build from this plan", "implement this storyboard", "turn this scene plan into Manim", or after running /scene-plan.
version: 1.0.1
argument-hint: " [build-handoff]"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep]
---

# Scene Build

Implement Manim code from a scene plan.

## Preconditions

- Expect a scene plan in the current conversation.
- If no plan is present, ask for one short planning pass first instead of improvising a complex scene.

## Build workflow

1. Read the provided scene plan.
2. Preserve the beat order unless render/debug issues require a small change.
3. Write one main `scene.py` file unless the user explicitly asks for more.
4. Keep one main `Scene` class unless there is a strong reason to split.
5. Use `layout-safety` on dense beats as an advisory audit before the final render pass.
6. Render, inspect, and simplify if the result feels crowded.

## Beat-to-code mapping

- Each beat should correspond to one visible stage in `construct()`.
- Prefer comments that mark beat boundaries.
- Keep each beat focused on one reveal, transform, or emphasis change.
- Keep narration aligned to the current beat.

## Quality checks

- Confirm the code matches the planned beat order.
- Confirm labels stay near the objects they describe.
- Confirm dense beats have been reviewed with the geometry-based layout safety check when the composition is crowded.
- Confirm there is a clear ending frame.
- Confirm the final narration covers all beats in order.

## Animation build rules (how to write play() calls)

### CJK text rendering — mandatory rules

Manim has three text rendering engines with incompatible character support:

| Engine | Class | CJK support | Use for |
|--------|-------|------------|--------|
| Pango | `Text()` | **Native** | All Chinese/Japanese/Korean text |
| LaTeX | `Tex()` | Needs XeLaTeX config | English text with LaTeX formatting |
| LaTeX math | `MathTex()` | **No Chinese** | Mathematical formulas only |

**Mandatory rules:**
- Chinese characters → **always use `Text()`**, never `Tex()` or `MathTex()`.
- Math formulas → always use `MathTex()`, never mix Chinese into it.
- Mixed Chinese+math line → combine `Text()` + `MathTex()` in a `VGroup`:
  ```python
  VGroup(Text("其中"), MathTex(r"x = \sqrt{2}")).arrange(RIGHT, buff=0.1)
  ```
- Do not specify custom `font` for `Text()` unless necessary; Pango auto-selects
  a CJK-capable system font.

### Animation duration bounds

Every `self.play()` call should specify or imply a reasonable duration:

| Animation type | Min | Recommended | Max |
|---------------|-----|-----------|-----|
| `FadeIn`, `FadeOut` | 0.3 s | **0.5–0.8 s** | 1.5 s |
| `Create` (draw shape) | 0.5 s | **1.0–1.5 s** | 3 s |
| `Write` (write text) | 1.0 s | **1.5–2.0 s** | 4 s |
| `Transform` / `ReplacementTransform` | 1.0 s | **1.5–2.5 s** | 4 s |
| `GrowFromCenter` / `GrowFromEdge` | 0.4 s | **0.8–1.2 s** | 2 s |
| `Indicate` / `Flash` / `Circumscribe` | 0.3 s | **0.5–1.0 s** | 1.5 s |
| `Shift` / `ApplyMethod` | 0.3 s | **0.5–1.0 s** | 2 s |
| `Wait` | 0.1 s | **0.3–0.8 s** | 1.5 s |

Duration estimation formula:
```
animation_seconds ≈ narration_char_count × 0.15
```
(Chinese: ~15 chars per spoken second in normal pace)

### Animation composition patterns

How to combine multiple animations in one `play()` call:

| Pattern | When to use | Example |
|---------|-------------|---------|
| Multiple args to `play()` | 2–3 independent simultaneous changes | `self.play(FadeIn(a), Transform(b, c))` |
| `AnimationGroup()` | Need explicit control over group timing | `self.play(AnimationGroup(anim1, anim2, lag_ratio=0.1))` |
| `LaggedStart(*anims, lag_ratio=0.15)` | Cascade reveal of related elements | Labels appearing one by one after a formula |
| `Succession(anim1, anim2)` | Strict sequential (second starts after first ends) | Step 1 must fully complete before step 2 |
| Separate `play()` calls | Beats or phases with pauses between | `self.play(step1); self.wait(0.5); self.play(step2)` |

**Rules:**
- Never nest `AnimationGroup` more than 2 levels deep.
- Prefer separate `play()` calls over giant `AnimationGroup` for readability.
- Use `lag_ratio=0.1–0.2` for `LaggedStart`; higher values feel sluggish.

### Updater usage

Use `add_updater()` only for these scenarios:

| Scenario | Example | Do NOT use for |
|----------|---------|----------------|
| Label follows a moving point | Dot on curve, label tracks it | Static labels |
| Real-time value display | Coordinate readout updates each frame | One-time annotations |
| Proportional resize | Two segments maintain ratio as parent grows | Fixed layouts |

Pattern:
```python
# Label that follows a moving dot
label = MathTex(r"(x, y)").add_updater(lambda m: m.next_to(dot, UR))
self.add(label)
# ... later, when animation moves dot, label follows automatically
```

Remove updaters when no longer needed: `label.clear_updaters()`.

### Rate function defaults to set

When writing `self.play()`, explicitly set `rate_func` for non-obvious cases:

```python
# Default (safe) — omit or set rate_func=smooth
self.play(Create(circle))

# Reveals — ease out feels natural
self.play(FadeIn(text), run_time=0.6, rate_func=ease_out_cubic)

# Transforms — smooth both ends
self.play(Transform(a, b), run_time=2.0, rate_func=ease_in_out_sine)

# Emphasis — slight overshoot draws attention
self.play(Indicate(term), rate_func=ease_out_back)
```

## Component library usage

Prefer component functions over raw Manim API calls. Components handle CJK safety, consistent styling, and correct timing automatically.

### Do / Don't

| Pattern | Don't (raw API) | Do (component) |
|---------|-----------------|----------------|
| Chinese text | `Text("勾股定理").scale(0.6).set_color(WHITE)` | `cjk_title("勾股定理")` |
| Math formula | `MathTex(r"a^2+b^2").scale(1.0).set_color(BLUE)` | `math_line(r"a^2+b^2")` |
| Mixed CJK+math | `VGroup(Text("其中"), MathTex(r"x")).arrange(RIGHT)` | `mixed_text("其中", r"x")` |
| Subtitle | `Text("步骤1", font_size=24).set_color(GRAY)` | `subtitle("步骤1")` |
| Title card | Manual positioning + Write/FadeIn | `TitleCard.get_title_mobjects(title="...")` |
| Proof steps | Manual VGroup arrange + label Text objects | `ProofStepStack()` + `.add_step()` + `.build()` |
| Step labels | `Text("已知")` with manual styling | `StepLabel(StepKind.GIVEN)` → "已知" |
| Corner annotation | `Text("条件").to_corner(UL)` | `Callout.create("条件", corner=UL)` |
| Highlight box | `SurroundingRectangle(target, ...)` | `HighlightBox.outline(target)` |
| Vertex labels | Multiple `MathTex().next_to()` calls | `LabelGroup()` + `.add_vertex("A", pt)` + `.build()` |
| Animation timing | Guessing `run_time=1.5` | `reveal(obj)`, `write_in(obj)`, `emphasize(obj)` — auto-timed |
| Buffer values | Hardcoded `buff=0.25` | `BUFFER.MED_SMALL`, `BUFFER.LARGE` etc. |
| Colors | Hardcoded `color=BLUE` | `COLOR_PALETTE.given`, `COLOR_PALETTE.highlight` etc. |

### When components don't cover your need

For patterns not yet in the component library:
1. Use raw Manim API but import constants from `components.config` for consistency.
2. Follow CJK rules from the table above (Chinese → `Text()`, math → `MathTex()`).
3. Use `BUFFER.*` and `COLOR_PALETTE.*` instead of magic numbers/colors.

## Use references only when needed

- For code style and render hygiene, read `../manim-production/references/code-style.md`.
- For math layout and emphasis, read `../manim-production/references/math-visualization-guidelines.md`.
- For spatial composition, screen zones, element sizing, color palette, and per-mode layout templates, read `../manim-production/references/spatial-composition.md`.
- For animation selection, rate functions, timing, composition patterns, and motion craft, read `../manim-production/references/animation-craft.md`.
- For render quality presets, caching behavior, file size budgeting, performance bottlenecks, and renderer selection, read `../manim-production/references/render-quality.md`.
- For the 3Blue1Brown visual style profile (exact color hex codes, LaTeX template config, animation speed/easing preferences), read `../manim-production/references/style-3b1b.md`.
- For common implementation mistakes and error-fix patterns, read `references/build-anti-patterns.md`.

## Implementation handoff

When used inside the main pipeline, return implementation facts through the
runtime-provided structured output schema. Do not redefine the schema in this
skill.

The handoff should make these facts clear:

- What was built.
- Whether the render succeeded.
- Any deviation from the original scene plan.
- The final scene class name.
- Which planned beats were actually implemented, in order.
- A short build summary.
