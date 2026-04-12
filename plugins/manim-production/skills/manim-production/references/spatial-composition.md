# Spatial Composition Reference for Manim Scenes

This reference covers how to arrange elements on screen so the result looks
professional and pedagogically effective.  It is based on Manim's coordinate
system, layout API, and common visual design principles for educational math
animations.

## Manim Coordinate System Quick Reference

```
                    UP (0, +1)
                      |
    UL (-7, +4) ------ UR (+7, +4)
    LEFT (-7, 0) -- ORIGIN (0, 0) -- RIGHT (+7, 0)
    DL (-7, -4) ------ DR (+7, -4)
                      |
                    DOWN (0, -1)
```

- **Frame dimensions**: ~14.22 wide x 8.0 tall (1080p default)
- **Origin** at center; Y points up
- **Safe zone**: stay within ~6.5 horizontally and ~3.5 vertically for content
- **Edge buffer**: `to_edge(UP)` places top at y ≈ +3.5 (not the literal edge)

### Common Position Constants

| Location | Approximate coords | Typical use |
|----------|-------------------|-------------|
| `ORIGIN` | (0, 0) | Main focal object |
| `2*UP` | (0, 2) | Title / heading |
| `3*UP` | (0, 3) | Large title |
| `2*DOWN` | (0, -2) | Footer / caption |
| `3*LEFT` | (-3, 0) | Left-side annotation |
| `3*RIGHT` | (3, 0) | Right-side annotation |
| `2*UP + 3*LEFT` | (-3, 2) | Upper-left callout |
| `2*UP + 3*RIGHT` | (3, 2) | Upper-right callout |

### Buffer Values

```python
SMALL_BUFF = 0.1        # Tight spacing (adjacent related items)
MED_SMALL_BUFF = 0.25   # Default next_to() gap
MED_LARGE_BUFF = 0.5    # Edge/corner margin
LARGE_BUFF = 1.0        # Section separation
```

## Screen Zone Map

Divide the frame into logical zones and assign content types to each:

```
+--------------------------------------------------+
|  TITLE ZONE (y > 2.5)                             |
|  Scene title, topic label, current beat indicator    |
+--------------------------------------------------+
|                                                  |
|  MAIN CONTENT ZONE (|y| < 2.5, |x| < 5)          |
|  Focal formula, central diagram, graph area         |
|  This is where the viewer's eye should rest         |
|                                                  |
+--------------------------------------------------+
|  LEFT ANNOTATION     |      RIGHT ANNOTATION       |
|  (x < -4)            |      (x > 4)               |
|  Given info,        |      Transformation notes,  |
|  input values,       |      result highlights,     |
|  condition labels    |      legend                  |
|                                                  |
+--------------------------------------------------+
|  FOOTER ZONE (y < -2.5)                            |
|  Subtitle, source citation, "Step N of M"          |
+--------------------------------------------------+
```

### Zone Rules

- **Title zone**: One short Text or Tex only. Never place formulas here.
- **Main zone**: Single dominant element per beat. This is the focal point.
- **Annotation zones**: Supporting labels, givens, legends. Keep text small.
- **Footer zone**: Optional. Use sparingly.

## Per-Mode Layout Templates

### Proof Walkthrough — Vertical Stack

Proofs read top-to-bottom. Use vertical arrangement with left annotations.

```
  [Title: "Proof: Pythagorean Theorem"]

  [Given:] a² + b² = c² ?        [Right side: diagram]
                                    ____
                                   |    |
  [Step 1:] a² + b²              | /\ |
  [Step 2:] = c² · sin²(θ)       |/  \|
  [Step 3:] = c²                 |____|

  [Q.E.D.] ✓
```

**Implementation pattern:**
```python
# Left column: proof steps (vertically stacked)
steps = VGroup(
    MathTex(r"a^2 + b^2"),
    MathTex(r"= c^2 \cdot \sin^2(\theta)"),
    MathTex(r"= c^2"),
).arrange(DOWN, aligned_edge=LEFT, buff=MED_SMALL_BUFF)
steps.to_edge(LEFT, buff=LARGE_BUFF).shift(DOWN * 0.5)

# Right side: geometric figure
figure = /* ... */
figure.to_edge(RIGHT, buff=LARGE_BUFF)

# Labels for each step (small, to the right of each line)
label1 = Text("Given").scale(0.4).next_to(steps[0], RIGHT, buff=SMALL_BUFF)
```

**Key rules:**
- Align all equals signs vertically (`aligned_edge=LEFT`)
- Space between steps: `MED_SMALL_BUFF` (0.25)
- Diagram on the right, proof text on the left
- Final conclusion centered or slightly below the stack

### Function Visualization — Graph-Centered

Graphs need axes as the frame, with curve and labels inside.

```
  [Title: "f(x) = x²"]

  [-6,-3]--------[0,0]--------[6,3]    <- Axes frame
           \     |     /
            \    |    /                <- Curve
             \   |   /
              \  |  /

  (0, 0)  vertex                   (3, 9)  point
```

**Implementation pattern:**
```python
axes = Axes(
    x_range=[-6, 6],
    y_range=[-3, 5],
    axis_config={"include_numbers": True},
).scale(0.85)  # Leave room for title and labels

graph = axes.plot(lambda x: x**2, color=BLUE)

# Labeled points on the curve
dot = Dot(axes.c2p(3, 9), color=YELLOW)
label = MathTex(r"(3, 9)").scale(0.6).next_to(dot, UR, buff=SMALL_BUFF)

# Title above axes
title = Text("f(x) = x²").to_edge(UP, buff=MED_LARGE_BUFF)
```

**Key rules:**
- Axes occupy ~70% of frame width and height
- Scale axes to 0.8-0.9 to leave margins
- Place labeled points with `next_to(point, direction, SMALL_BUFF)`
- Title always in title zone, never overlapping axes
- Legend (if needed) in lower-right corner

### Geometry Construction — Central Figure

Geometry scenes have one main figure with peripheral marks.

```
            A
           /\
          /  \
         /____\
        B      C

  ∠A = 60°     AB = c     [Right: angle arc]
```

**Implementation pattern:**
```python
# Central figure — slightly smaller than full frame
triangle = Polygon(A, B, C).scale(0.75)

# Vertex labels — outside the figure, close to vertices
label_a = Text("A").next_to(A, UL, buff=SMALL_BUFF)
label_b = Text("B").next_to(B, DL, buff=SMALL_BUFF)
label_c = Text("C").next_to(C, DR, buff=SMALL_BUFF)

# Angle/length annotations — on the sides, not overlapping figure
angle_arc = Angle(Line(B, A), Line(C, A), radius=0.4)
angle_label = MathTex(r"60^\circ").next_to(angle_arc, RIGHT, buff=SMALL_BUFF)
```

**Key rules:**
- Figure at 0.7-0.8 scale to leave room for labels
- Vertex labels placed diagonally outward from each vertex (`UL`, `DL`, `DR`, `UR`)
- Angle arcs use `radius=0.3-0.5` (small enough to not overlap figure)
- Length/equality marks on the edges, not inside the shape

### Concept Explainer — Centered Diagram with Callouts

Concept explanations use a central visual with surrounding context.

```
  [Title: "What is a Derivative?]

       [Before: secant line]
              \
               \  slope = Δy/Δx
                \

  [Central: curve tangent] -----> [After: tangent line]
                                     |
                               [Label: "instantaneous rate"]
```

**Implementation pattern:**
```python
# Central element at origin
main_diagram = /* ... */.move_to(ORIGIN)

# Surrounding elements in corners / edges
before_label = Text("Before").scale(0.5).to_corner(UL, buff=MED_LARGE_BUFF)
after_label = Text("After").scale(0.5).to_corner(UR, buff=MED_LARGE_BUFF)
detail = Text("slope = Δy/Δx").scale(0.45).to_edge(RIGHT, buff=MED_LARGE_BUFF)
```

**Key rules:**
- Central diagram at or near ORIGIN, occupying main content zone
- Context labels in corners (using `to_corner`) or edges (using `to_edge`)
- Keep callout text at scale 0.4-0.5 (smaller than main content)
- Max 3-4 callouts per beat to avoid clutter

## Element Sizing Guidelines

### Text and Formula Sizes

| Element type | Default scale | Recommended range | When to adjust |
|-------------|---------------|-------------------|----------------|
| `Text()` title | 1.0 | 0.8–1.2 | Shorten if > 15 chars |
| `Text()` body | 0.6 | 0.45–0.7 | Smaller for annotations |
| `MathTex()` main | 1.0 | 0.8–1.5 | Larger for key formulas |
| `MathTex()` inline | 0.6 | 0.45–0.7 | Side annotations |
| `Tex()` label | 0.5 | 0.35–0.6 | Axis labels, legends |

### Readability Floor

At 1080p resolution:
- **Minimum readable scale**: ~0.35 for `Text()`, ~0.4 for `MathTex()`
- Below this, text becomes illegible on video export
- If you need smaller text, consider moving it to narration instead

### Proportion Rules

- **Label : annotated object ratio**: Label should be 30–60% the width of what it labels
- **Title : content ratio**: Title height ≤ 15% of frame height
- **Annotation : main content ratio**: Annotations should occupy ≤ 25% of frame area combined

## Color Palette for Educational Content

Use colors semantically. Recommended palette (4 core + neutral):

| Color | Manim constant | Semantic use |
|-------|---------------|-------------|
| Blue | `BLUE` | Given information, input values, original state |
| Yellow | `YELLOW` | Highlights, focal emphasis, key results |
| Green | `GREEN` | Conclusions, correct answers, final states |
| Red | `RED` | Transformations, changes, errors, warnings |
| White | `WHITE` | Neutral text on dark background |
| Gray | `GRAY` | De-emphasized elements, secondary info |

### Color Rules

- **Max 4-5 distinct colors per scene** (excluding WHITE/GRAY)
- **Same variable = same color** throughout the entire video
- **Background**: default black is fine; use custom only for special effects
- **Contrast**: avoid yellow-on-white or light-blue-on-white combinations
- **CJK text**: use `Text()` (Pango renderer) not `Tex()`/`MathTex()` (LaTeX) for Chinese characters

## Mobject Selection Guide

| Visual need | Recommended mobject | Avoid |
|------------|---------------------|-------|
| Plain text (esp. CJK) | `Text()`, `MarkupText()` | `Tex()` (no CJK) |
| Math formula | `MathTex()` | `Text()` (no math rendering) |
| Mixed math+text | `Tex()` or separate `Text` + `MathTex` | — |
| Highlight region | `SurroundingRectangle` | Hand-drawn boxes |
| Background emphasis | `BackgroundRectangle` | Changing background color |
| Group for layout | `VGroup()` (VMobjects) | `Group()` (slower) |
| Annotated brace | `Brace()` + `BraceText()` | Manual lines |
| Directional arrow | `Arrow()`, `Vector()` | `Line()` with tips |
| Labeled point | `Dot()` + `MathTex().next_to()` | Just coordinates |
| Angle mark | `Angle()` + `RightAngle()` | Manual arcs |

## Animation Timing Guidelines

Connect animation duration to narration length:

| Narration length | Animation duration | Technique |
|-----------------|-------------------|-----------|
| < 2 seconds | 0.5–1 s | Quick FadeIn, instant highlight |
| 2–5 seconds | 1–3 s | Create, Transform, GrowFromEdge |
| 5–10 seconds | 3–6 s | Multi-step reveal, Write, ShowPassingFlash |
| > 10 seconds | 5–10 s | Complex multi-object animation sequence |

### Animation Motion Preferences

- **Reveals**: prefer `FadeIn`, `GrowFromCenter`, `Create` over sudden appearance
- **Transformations**: prefer `Transform`, `ReplacementTransform` over disappear+reappear
- **Emphasis**: prefer `Indicate`, `ShowPassingFlash`, `SurroundingRectangle` over color flash
- **Movement**: prefer smooth paths; avoid diagonal streaks unless intentional
- **Simultaneous vs sequential**: animate related items together (max 3 simultaneous); sequence unrelated items

## Layout Anti-Patterns (Positive Alternatives)

| Anti-pattern | Why it fails | Positive alternative |
|-------------|-------------|---------------------|
| All elements at `ORIGIN` | Overlapping chaos | Use zones: main at center, annotations at edges |
| Hard-coded coordinates like `(3.14, 2.71)` | Fragile, unreadable | Use relative: `next_to()`, `align_to()`, `to_edge()` |
| Everything at `scale(1.0)` | No hierarchy | Main content 0.8–1.0, annotations 0.4–0.6 |
| 6+ colors in one scene | Confusing | Stick to 3–4 semantic colors max |
| Full-width `MathTex` spanning entire frame | Crowds out everything else | `scale_to_fit_width(8)` or break into parts |
| Labels far from their objects | Viewer loses connection | `next_to(obj, direction, buff=SMALL_BUFF)` |
| No title in opening beat | Disorienting | Always include topic identifier in first 2 beats |
| Empty right half of screen | Unbalanced, wasteful | Distribute content: left=givens, right=result/diagram |
