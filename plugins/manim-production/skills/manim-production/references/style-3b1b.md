# 3b1b (ThreeBlueOneBrown) Style Profile

This reference documents the visual style characteristics of Grant Sanderson's
3Blue1Brown educational math videos, mapped to concrete Manim configuration
values extracted from the installed Manim package source code.

All color values below are **exact hex codes** from `manim/utils/color/manim_colors.py`.
The 3b1b LaTeX template is from `manim/utils/tex_templates.py`.

## Color Palette

### Core palette

| Role | Color | Hex | Source |
|------|-------|-----|--------|
| Background | Dark blue-black | `#050A14` | 3b1b convention (not a Manim default) |
| Primary text / main objects | White | `#FFFFFF` | VMobject default |
| Primary accent | Blue | `#58C4DD` | Manim's `BLUE_C` |
| Secondary accent | Green | `#83C167` | Manim's `GREEN_C` |
| Highlight / emphasis | Gold yellow | `#F7D96F` | Manim's `YELLOW_C` |
| Warning / transformation | Red | `#FC6255` | Manim's `RED_C` (also Circle default) |
| Dimmed / de-emphasized | Gray | `#888888` | Manim's `GRAY_C` |
| Very dim | Dark gray | `#444444` | Manim's `GRAY_D` |

### Semantic color mapping for math education

```
Given information, input values          → BLUE_C (#58CDDD)
Transformations, changes               → RED_C (#FC6255) or YELLOW_C (#F7D96F)
Results, conclusions                   → GREEN_C (#83C167)
Temporary highlights                    → GOLD_B (#F9B775) or YELLOW_C
Annotations, labels                     → WHITE (#FFFFFF) at reduced opacity
De-emphasized / background info        → GRAY_C (#888888) or GRAY_D (#444444)
```

**Rule**: Never use more than 4-5 distinct colors (excluding white/gray/black)
in one scene.  Reuse colors consistently: the same variable always gets the same color.

## Background Configuration

```python
# In Scene config or global config:
config.background_color = "#050A14"  # Deep dark blue (not pure black)
config.background_opacity = 1.0
```

Why not pure black (`#000000`):
- Pure black looks flat and harsh on screen
- `#050A14` has subtle depth; feels like "space"
- Matches the 3b1b aesthetic of a dark void where mathematics lives

## Typography

### Font choices (from 3b1b LaTeX template)

The 3b1b template (`TexTemplateLibrary.threeb1b`) uses this LaTeX preamble:

```latex
\usepackage[english]{babel}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}        % T1 font encoding (better symbol support)
\usepackage{lmodern}              % Latin Modern (clean mathematical font)
\usepackage{amsmath}, {amssymb}   % Standard math packages
\usepackage{dsfont}                % DS font (for custom symbols)
\usepackage{setspace}
\usepackage{tipa}                 % Tips and annotations
\usepackage{relsize}             % Relative sizing
\usepackage{textcomp}            % Text comparison
\usepackage{mathrsfs}            % Math rsfs (script-style letters)
\usepackage{calligra}             % Calligraphic (decorative letters)
\usepackage{wasysym}             # WAS symbols
\usepackage{physics}              % Physics notation
\usepackage{xcolor}
\usepackage{microtype}            % Micro-typography
\DisableLigatures{encoding = *, family = * }  % Disable ligatures
\linespread{1}                  % Slightly loose line spacing
```

Key implications:
- **Latin Modern** is the math font — clean, professional, highly readable
- **T1 encoding** — proper symbol rendering (ℕ → \ell, etc.)
- **Ligatures disabled** — prevents unwanted character merging
- **Slightly loose spacing** — easier to read at small sizes

### For Text() (Pango-based, non-LaTeX)

```python
# Chinese text (always use Text(), never Tex/MathTex for CJK):
Text("导数", font_size=42, color=WHITE)

# English labels:
Text("slope", font_size=36, color=BLUE_C)

# Small annotations:
Text("Q.E.D.", font_size=28, color=GRAY_C)
```

### Font size hierarchy (at 1080p resolution)

| Element | Scale / font_size | Visual size on screen |
|--------|-------------------|----------------------|
| Title | 60–72 px (~scale 1.2–1.5) | Large, prominent |
| Main formula | Default (48px) | Easy to read |
| Body label | 36–42 px (~scale 0.75) | Clear but not dominant |
| Annotation | 24–30 px (~scale 0.5–0.6) | Supporting role |
| Tiny / footnote | 18–24 px (~scale 0.35–0.45) | Minimal |

## Geometry & Shape Defaults

From Manim source defaults:

| Mobject | Default fill | Default stroke | Notes |
|----------|-------------|---------------|-------|
| `Circle()` | `RED` (#FC6255) | `None` (filled) | Red circle — use `color=BLUE_C` instead |
| `Polygon()` | `BLUE` (#58C4DD) | `None` (filled) | Blue polygon — good default |
| `Rectangle()` / `Square()` | `WHITE` (#FFFFFF) | `None` (filled) | White rectangle — use with `color=BLUE_D` |
| `Line()` | `WHITE` | Width = 4 | White line — add `color=GRAY_C` |
| `Dot()` | `WHITE` | Radius varies | White dot — use `color=YELLOW_C` for emphasis |
| `Arrow()` | `WHITE` | Width = 4 | White arrow — use `color=GRAY_C` for neutral |

**3b1b overrides**: Always set explicit colors. Never rely on defaults.

## Animation Style Characteristics

### Speed

3b1b animations tend to be **slightly faster than Manim defaults**:

| Animation type | 3b1b typical duration | Manim default | Adjustment |
|--------------|----------------------|---------------|-----------|
| FadeIn / reveal | 0.4–0.6 s | 1.0 s | Shorter — confident appearance |
| Transform / morph | 1.5–2.5 s | 1.0–2.0 s | Similar or slightly longer |
| Write (text writing) | 1.0–1.8 s | 1.0–1.5 s | Similar |
| Emphasis (Indicate) | 0.5–0.8 s | 1.0 s | Crisper — quick pop |
| Wait (pause) | 0.3–0.6 s | 1.0 s | Much shorter — keeps momentum |

### Easing preferences

3b1b animations feel smooth because they favor **ease-out** functions:

| Situation | 3b1b preference | Rationale |
|----------|----------------|-----------|
| Objects appearing | `ease_out_cubic` | Fast start → gentle stop = natural "materializing" |
| Objects transforming | `ease_in_out_sine` | Both ends soft = fluid morphing |
| Emphasis moments | `ease_out_back` | Slight overshoot catches eye |
| Continuous motion | `smooth` (sigmoid) | Never jarring |
| Disappearing | `ease_in_cubic` | Slow fade = gentle exit, not abrupt cut |

### Camera usage

3b1b uses camera movement **sparingly but intentionally**:

- **Zoom in**: When revealing detail in a complex formula after showing overview
- **Pan**: When transitioning between spatially separated diagram regions
- **Reset**: Always return to full view after zoom — never end zoomed in
- **No rotation**: 3b1b almost never rotates the coordinate system
- **Max 1–2 camera movements per scene** — more feels seasick

## Compositional Patterns Specific to 3b1b

### The "Glow" effect

3b1b scenes often have a subtle glow around key elements.
Achieve in Manim via:

```python
from manim.mobject.geometry.shape_matchers import SurroundingRectangle

# Soft highlight box with low-opacity background
glow = BackgroundRectangle(
    target_formula,
    fill_opacity=0.08,
    color=BLUE_C,
    buff=0.15,
)
self.play(FadeIn(glow), run_time=0.8)
```

Use opacity 0.05–0.15 for subtle glow; 0.2+ for strong emphasis.

### Label placement conventions

3b1b labels follow consistent patterns:

- **Variable labels**: Below or to the right of the variable, slightly smaller
- **Value labels**: Near the point being labeled, offset by SMALL_BUFF
- **Equation group labels**: Underneath, centered, connected by Brace
- **Dimension labels**: Along the dimension line, using smaller font
- **All labels**: White or light gray on dark background; never compete with content color

### The "linger" pattern

After a transformation completes, 3b1b often shows both old and new briefly,
then shrinks old to corner:

```python
old = original.copy()
self.play(
    Transform(original, new),
    old.animate.scale(0.5).to_corner(DL).set_opacity(0.5),
    run_time=2.0,
)
# Both visible during transform; old fades to corner afterward
self.wait(0.5)
# Now only new remains prominent, old is small reference in corner
```

## Complete Style Configuration Block

Put this at the top of your scene file or in a shared config:

```python
from manim.utils.color import manim_colors as C
from manim.utils.tex import TexTemplate, TexTemplateLibrary

# ── Colors ──
BG = "#050A14"           # Dark background (3b1b signature)
TEXT = C.WHITE
MATH = C.WHITE
PRIMARY = C.BLUE_C       # #58C4DD
SECONDARY = C.GREEN_C   # #83C167
ACCENT = C.YELLOW_C     # #F7D96F
WARN = C.RED_C         # #FC6255
DIM = C.GRAY_C         # #888888
DIM2 = C.GRAY_D        # #444444

# ── LaTeX Template (3b1b style) ──
TEX_TEMPLATE = TexTemplateLibrary.threeb1b

# ── Common styled object factory ──
def StyledMath(tex_string, *, color=MATH, **kwargs):
    return MathTex(tex_string, tex_template=TEX_TEMPLATE, color=color, **kwargs)

def StyledLabel(text_string, *, color=DIM, font_size=28, **kwargs):
    return Text(text_string, color=color, font_size=font_size, **kwargs)

def StyledTitle(text_string, *, color=TEXT, font_size=56, **kwargs):
    return Text(text_string, color=color, font_size=font_size, weight=BOLD, **kwargs)
```

## Quality Settings for 3b1b Output

```bash
# Development / iteration (fast):
manim -qm scene.py          # 720p30fps — fast renders

# Final production (3b1b standard is 1080p60fps):
manim -qh scene.py          # 1080p60fps — matches YouTube HD

# If hosting on 4K platform:
manim -qk scene.py          # 3840p2160 — presentation quality
```

3b1b uploads at 1080p60fps typically. This is Manim's `high_quality`
preset — no special configuration needed beyond `-qh`.

## Quick Reference Card

```
BACKGROUND:   #050A14 (dark blue, not pure black)
TEXT/MATH:    #FFFFFF (white)
PRIMARY:      #58C4DD (blue_c)
SECONDARY:    #83C167 (green_c)
HIGHLIGHT:     #F7D96F (yellow_c)
WARNING:       #FC6255 (red_c)
DIM:           #888888 (gray_c)
STROKE_WIDTH: 4 (default)
FONT (math):    Latin Modern (via 3b1b1b template)
FONT (text):    System Pango default (CJK-native)
QUALITY:       -qh (1080p60fps) for final
ANIM SPEED:    Slightly faster than defaults (reveals ~0.5s, transforms ~2s)
EASING:        ease_out for appears, ease_in_out for transforms, ease_out_back for emphasis
CAMERA:        Max 1-2 movements per scene; always reset; never rotate
LABEL RULE:    Chinese→Text(), Math→MathTex(), never mix; white/dim on dark bg
MAX COLORS:    4-5 per scene + white/gray/black
```
