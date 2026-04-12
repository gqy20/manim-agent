# Animation Craft — Manim 动画工艺手册

This is the motion/time companion to `spatial-composition.md`.  While that document
covers **where** things go on screen, this covers **how** they move, appear,
transform, and disappear.

## 1. Animation Class Quick Reference

### Creation (appearing)

| Class | What it does | Default run_time | Typical rate_func |
|-------|-------------|-----------------|-------------------|
| `FadeIn` | Opacity 0→1 | 1.0 | `smooth` |
| `Create` | Stroke-draw a VMobject (like pen tracing) | 1.0 | `linear` |
| `Write` | Stroke-draw text character by character | 1.0 | `linear` |
| `GrowFromCenter` | Scale from 0 at center | 1.0 | `smooth` |
| `GrowFromEdge` | Scale from 0 from an edge direction | 1.0 | `smooth` |
| `DrawBorderThenFill` | Draw outline first, then fill interior | 2.0 | `smooth` |
| `SpiralIn` | Spiral inward into position | 1.0 | `smooth` |
| `ShowIncreasingSubsets` | Reveal progressively more submobjects | 1.0 | `smooth` |

### Disappearing

| Class | What it does | Default run_time | Note |
|-------|-------------|-----------------|------|
| `FadeOut` | Opacity 1→0 (removes from scene) | 1.0 | Use for temporary elements only |
| `Uncreate` | Reverse of Create (trace disappears) | 1.0 | Nice "undo" effect |
| `ShrinkToCenter` | Scale down to point at center | 1.0 | Good for dismissal |

### Transformation (changing shape/position)

| Class | What it does | Key params | Use case |
|-------|-------------|------------|---------|
| `Transform` | Morph A into B | `path_arc`, `replace_mobject_with_target_in_scene` | Shape morphing |
| `ReplacementTransform` | Replace A with B in scene | — | Clean swap |
| `FadeTransform` | Cross-fade A→B | — | Soft transition |
| `ScaleInPlace` | Scale without moving | — | Emphasis pulse |
| `ApplyMethod` | Call method on mobject over time | — | Programmatic change |
| `Homotopy` | Continuous pointwise transform | — | Advanced morphing |

### Movement

| Class | What it does | Use case |
|-------|-------------|---------|
| `MoveAlongPath` | Follow a curved path | Tracing curves |
| `Rotate` | Spin around a point or axis | Angular motion |

### Indication / Emphasis

| Class | What it does | Visual effect | Duration |
|-------|-------------|---------------|----------|
| `Indicate` | Briefly scale + color flash | Object "pops" | ~0.8 s |
| `Flash` | Quick radial flash on point | Sparkle / highlight moment | ~0.5 s |
| `ShowPassingFlash` | Line of light sweeps across object | Scan / trace | ~1.0 s |
| `Circumscribe` | Draw expanding circle around object | Circle / focus mark | ~1.0 s |
| `FocusOn` | Spotlight / dim surroundings | Isolate attention | ~1.0 s |
| `Wiggle` | Small oscillation | Playful / uncertain | ~0.5 s |
| `ApplyWave` | Wave distortion across object | Fluid / field effect | ~1.5 s |

### Specialized

| Class | What it does | Domain |
|-------|-------------|---------|
| `ChangeDecimalToValue` | Animate number counting up/down | Data visualization |
| `CountInScene` | On-screen counter animation | Counting |
| `Rotate` | Continuous or fixed rotation | Geometry |

## 2. Rate Function (Easing) Guide

Manim provides 30+ rate functions in `manim.utils.rate_functions`.
**90% of the time, use `smooth`.**  The remaining 10%:

### By animation purpose

```
Reveals (FadeIn, Create, Write, GrowFrom*)
  → ease_out_cubic     # Fast start, gentle stop = natural appearance
  → ease_out_quad      # Simpler variant
  → smooth              # Safe default

Transforms (Transform, ReplacementTransform)
  → ease_in_out_sine    # Both ends soft; good for shape morphing
  → ease_in_out_cubic   # Stronger easing
  → smooth              # Safe default

Emphasis (Indicate, Flash, Circumscribe)
  → ease_out_back       # Slight overshoot draws eye
  → ease_out_elastic    # Bouncy; high energy
  → there_and_back      # Pulse then return

Mechanical / linear motion (Shift along axis)
  → linear              # Constant speed
  → ease_in_out_quad    # Gentle acceleration curve

"Go away and come back" (temporary highlight)
  → there_and_back      # Full cycle: 0→1→0
  → there_and_back_with_pause  # Same but lingers at peak
```

### Visual intuition (speed over time)

```
ease_in_cubic:    ███░░░░░░░  (slow start, fast end) ← BAD for reveals
ease_out_cubic:   ░░░░░░███    (fast start, slow end) ← GOOD for reveals
ease_in_out_sine:  ████░████    (both ends slow) ← GOOD for transforms
linear:            ██████████    (constant speed) ← mechanical
smooth:            ██████████    (sigmoid, nearly same as linear for most cases)
ease_out_back:    ██████▀██    (overshoots slightly) ← emphasis
ease_out_elastic: █████▒█▒█    (bounces) ← playful emphasis
wiggle:           ▄█▄█▄█▄█      (oscillation) ← uncertainty / alive
```

### Quick decision tree

```
Is this a reveal (something appearing)?
  YES → ease_out_cubic (or just omit = smooth default)
  
Is this a transformation (A becomes B)?
  YES → ease_in_out_sine
  
Is this emphasis (draw attention to existing thing)?
  YES → ease_out_back (subtle) or ease_out_elastic (bold)
  
Is this mechanical movement?
  YES → linear
  
Not sure?
  → smooth (never wrong)
```

## 3. Animation Composition Patterns

### Pattern A: Parallel reveal (simultaneous)

```python
# Two things appear together — use when they're contextually linked
self.play(
    FadeIn(formula),
    GrowFromCenter(diagram),
    run_time=1.5,
)
# Both finish at the same time; total duration = run_time
```

### Pattern B: Cascade reveal (LaggedStart)

```python
# Elements appear one after another with overlap — natural rhythm
self.play(
    LaggedStart(
        FadeIn(label_a),
        FadeIn(label_b),
        FadeIn(label_c),
        lag_ratio=0.15,  # Each starts 15% of duration after previous
    ),
    run_time=2.0,
)
# Total ≈ 2.0 + 2 × 0.15 × 2.0 = 2.6 s of visible activity
```

**When to use**: Revealing parts of a formula, listing givens, showing steps.

### Pattern C: Strict sequential (Succession)

```python
# One must fully complete before next begins
self.play(
    Succession(
        Write(step1),          # Must finish completely
        Transform(step1, step2),  # Then this starts
        FadeOut(arrow),         # Then this
    ),
    run_time=4.0,
)
```

**When to use**: Causal chain (step 1 causes step 2), proof derivation.

### Pattern D: Beat structure (separate play calls)

```python
# Most common pattern for multi-beat scenes
# Beat 1: Introduce
self.play(GrowFromCenter(main_obj), run_time=1.0)
self.wait(0.5)

# Beat 2: Annotate
self.play(FadeIn(label_1), FadeIn(label_2), run_time=0.6)
self.wait(0.3)

# Beat 3: Transform
self.play(Transform(original, modified), run_time=2.0)
self.wait(0.5)

# Beat 4: Emphasize result
self.play(Circumscribe(result, color=YELLOW), run_time=1.0)
self.wait(0.8)
```

**Why separate calls**: Each `play()` is a visual "sentence".  Pauses between them
are like periods — they let the viewer's eye catch up.

### Pattern E: Shrink-to-corner (visual persistence)

```python
# After a formula transforms, keep old version visible in corner
old_copy = formula.copy()
self.play(
    Transform(formula, new_formula),
    old_copy.animate.scale(0.45).to_corner(DL),  # Shrink to lower-left
    run_time=2.0,
)
# old_copy remains on screen as reference
```

## 4. Per-Mode Animation Templates

### Proof Walkthrough

Proof scenes read top-to-bottom.  Animation should reinforce that flow.

```python
def construct(self):
    title = Text("Proof: Pythagorean Theorem").to_edge(UP)
    self.add(title)

    # Step 1: Show given (reveal)
    given = MathTex(r"a^2 + b^2 = c^2")
    self.play(Write(given), run_time=1.5)
    self.wait(0.5)

    # Step 2: Introduce diagram (parallel context)
    triangle = RightTriangle().scale(0.7).to_edge(RIGHT)
    self.play(GrowFromCenter(triangle), run_time=1.2)
    self.wait(0.3)

    # Step 3: Label sides (cascade)
    labels = VGroup(
        MathTex(r"a").next_to(triangle.get_left(), LEFT, buff=SMALL_BUFF),
        MathTex(r"b").next_to(triangle.get_bottom(), DOWN, buff=SMALL_BUFF),
        MathTex(r"c").next_to(triangle.get_right() + triangle.get_top(), UR, buff=SMALL_BUFF),
    )
    self.play(LaggedStart(*[FadeIn(l) for l in labels], lag_ratio=0.12), run_time=1.2)
    self.wait(0.5)

    # Step 4: Transform equation step-by-step (sequential)
    step2 = MathTex(r"a^2 + b^2 = c^2 \cdot \sin^2(\theta)")
    self.play(Transform(given, step2), run_time=2.0, rate_func=ease_in_out_sine)
    self.wait(0.5)

    # ... more steps ...

    # Final: Q.E.D.
    qed = MathTex(r"\text{Q.E.D.}")
    self.play(Write(qed), run_time=1.0)
    self.play(Indicate(qed), rate_func=ease_out_back)
    self.wait(1.0)
```

**Key patterns**: `Write()` for equations, `LaggedStart` for label cascades,
`Transform` with `ease_in_out_sine` for equation evolution, `Indicate` + `ease_out_back`
for final emphasis.

### Function Visualization

Graph scenes are spatial-first; animation should guide the eye around the graph.

```python
def construct(self):
    title = Text("f(x) = x²").to_edge(UP)
    self.add(title)

    # Phase 1: Build axes first (foundation)
    axes = Axes(x_range=[-5, 5], y_range=[-3, 5]).scale(0.85)
    self.play(Create(axes), run_time=2.0)  # Drawing feels appropriate for axes
    self.wait(0.3)

    # Phase 2: Draw the curve (tracing path)
    graph = axes.plot(lambda x: x**2, color=BLUE)
    self.play(Create(graph), run_time=2.5, rate_func=ease_out_cubic)
    self.wait(0.5)

    # Phase 3: Mark key points (one by one)
    p1_dot = Dot(axes.c2p(-2, 4), color=YELLOW)
    p1_label = MathTex(r"(-2, 4)").scale(0.55)
    p2_dot = Dot(axes.c2p(3, 9), color=YELLOW)
    p2_label = MathTex(r"(3, 9)").scale(0.55)

    self.play(FadeIn(p1_dot), run_time=0.4)
    self.play(p1_label.animate.next_to(p1_dot, UR), run_time=0.5)
    self.wait(0.3)
    self.play(FadeIn(p2_dot), run_time=0.4)
    self.play(p2_label.animate.next_to(p2_dot, DR), run_time=0.5)
    self.wait(0.8)

    # Phase 4: Highlight relationship (emphasis)
    self.play(Indicate(graph), Indicate(p1_dot), run_time=1.0)
    self.wait(0.5)
```

**Key patterns**: `Create` for axes and curves (drawing feels foundational),
individual point reveals (not batched), short pauses between each annotation.

### Geometry Construction

Geometry scenes build figures progressively.

```python
def construct(self):
    # Phase 1: Base shape appears
    triangle = Polygon(A, B, C)
    self.play(DrawBorderThenFill(triangle), run_time=2.0)
    self.wait(0.3)

    # Phase 2: Vertex labels (from corners outward)
    labels = VGroup(
        Text("A").scale(0.55).next_to(A, UL, buff=SMALL_BUFF),
        Text("B").scale(0.55).next_to(B, DL, buff=SMALL_BUFF),
        Text("C").scale(0.55).next_to(C, DR, buff=SMALL_BUFF),
    )
    self.play(LaggedStart(*[GrowFromCenter(l) for l in labels], lag_ratio=0.15))
    self.wait(0.5)

    # Phase 3: Measurement marks (sequential, precise)
    angle_A = Angle(Line(B, A), Line(C, A), radius=0.4)
    angle_label = MathTex(r"60^\circ").scale(0.45)
    self.play(ShowCreation(angle_A), run_time=1.2)
    self.play(Write(angle_label), angle_label.animate.next_to(angle_A, RIGHT))
    self.wait(0.5)

    # Phase 4: Conclusion highlight
    self.play(Circumscribe(triangle, color=YELLOW), run_time=1.0)
    self.wait(0.8)
```

**Key patterns**: `DrawBorderThenFill` for shapes (border then fill is satisfying),
`GrowFromCenter` for labels (organic feel), `ShowCreation` for angles/arcs
(more precise than generic Create).

### Concept Explainer

Concept scenes use centered diagrams with surrounding callouts.

```python
def construct(self):
    title = Text("What is a Derivative?").to_edge(UP)
    self.add(title)

    # Central concept appears
    core = MathTex(r"\frac{dy}{dx} = \lim_{\Delta x \to 0} \frac{\Delta y}{\Delta x}")
    self.play(GrowFromCenter(core), run_time=1.5)
    self.wait(0.5)

    # Context callouts appear in corners (not crowding center)
    before = Text("Before: secant line").scale(0.45).to_corner(UL)
    after = Text("After: tangent line").scale(0.45).to_corner(UR)
    detail = Text("slope = Δy/Δx").scale(0.42).to_edge(RIGHT)
    self.play(
        FadeIn(before), FadeIn(after), FadeIn(detail),
        run_time=0.8,
    )
    self.wait(0.5)

    # Transform central concept
    transformed = MathTex(r"f'(x) = \lim_{h \to 0} \frac{f(x+h) - f(x)}{h}")
    self.play(Transform(core, transformed), run_time=2.5, rate_func=ease_in_out_sine)
    self.wait(0.8)

    # Final emphasis
    self.play(Indicate(transformed), run_time=0.8, rate_func=ease_out_back)
    self.wait(1.0)
```

## 5. Animation Anti-Patterns

| Anti-pattern | Why it fails | Fix |
|-------------|-------------|-----|
| `FadeIn` with `run_time=0.1` | Too fast to register; looks like a glitch | Minimum 0.4–0.5 s |
| `Wait(3.0)` or longer | Viewer thinks video froze; kills engagement | Max 1.5 s; prefer `Wait(0.5)` |
| Single `play()` with 6+ mobjects | Cognitive overload; looks like PPT | Split into 2–3 play+wait groups |
| All animations use default `rate_func` | Flat, monotonous rhythm | Vary: smooth for normal, ease_out for reveals, ease_out_back for emphasis |
| `Transform` without `rate_func` | Linear interpolation can look mechanical | Add `ease_in_out_sine` or `ease_in_out_cubic` |
| Every element uses `FadeIn` | No visual variety; boring | Mix: GrowFromCenter for main, FadeIn for secondary, Write for text |
| `FadeOut` important content | Information lost; viewer can't refer back | Shrink to corner at scale(0.4–0.5) instead |
| No `wait()` between beats | Rushed; no time to absorb | Always add `wait(0.3–0.8)` after each beat's play |
| Nested `AnimationGroup(AnimationGroup(...))` | Unreadable; timing bugs | Flatten to single level or use separate play() calls |
| `ease_in_*` on reveal animations | Object appears to accelerate into existence (unnatural) | Use `ease_out_*` for all appearance animations |
| Animating background color changes | Jarring; distracts from content | Keep background static unless intentional effect |
