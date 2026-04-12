---
name: scene-direction
description: Direct the visual language of a Manim scene so it feels like a guided explanation instead of a static slide deck. Use when improving opening beats, focal hierarchy, motion clarity, transformations, visual pacing, or ending payoff in educational animation tasks.
version: 1.0.1
argument-hint: " [scene-or-plan]"
allowed-tools: [Read, Glob, Grep]
---

# Scene Direction

Use this skill to shape how the animation feels on screen.

## Primary goals

- Make the first few seconds visually active, not just labeled.
- Keep one focal object, formula, or relationship per beat.
- Show conclusions through motion, transforms, or emphasis changes.
- Make the final beat feel like a payoff, not just a leftover summary card.

## Opening rules

- In the first 3 seconds, show both the topic and a visible object or graphic.
- Avoid opening with a title on an otherwise empty screen unless the task is a tiny one-beat demo.
- Prefer object-first or object-plus-title openings over title-only openings.
- Make the viewer understand what the animation is about before the first long pause.

## Beat direction rules

- Each beat should have one new visual idea only.
- Each beat should have one dominant focal point.
- Introduce new text only when it supports the focal object instead of competing with it.
- Prefer transforms, parameter changes, reveals, and highlighting over replacing the whole frame with a new static layout.
- If a conclusion matters, animate the transition that creates it.

## Density rules

- Keep one main formula or one main graphic per beat.
- Keep supporting text short.
- Move long explanations to narration instead of the canvas.
- If a frame feels crowded, simplify before adding more labels.

## Ending rules

- End on a stable takeaway frame.
- The ending should clearly resolve the question, construction, or proof introduced earlier.
- Prefer visual recall or a final highlighted relationship over a generic bullet summary.

## Motion direction rules (how things move)

The beat direction rules above define *what* appears *when*.  This section defines
*how* it appears — which animation type, easing, and rhythm to use.  Motion is
meaning: the way an object moves on screen is itself mathematical information.

### Motion = Meaning mapping

Choose animations that match the mathematical semantics of what you are showing:

| To convey | Use this animation | Avoid |
|-----------|-------------------|-------|
| Introducing a **new concept** | `GrowFromCenter`, `GrowFromEdge` | `FadeIn` (too abrupt) |
| A **derivation / step-by-step** process | `Write`, `Create` | Showing everything at once |
| An **equivalence** or **transformation** | `Transform`, `ReplacementTransform` | Disappear + reappear |
| Emphasizing a **key result** | `Indicate`, `Flash`, `Circumscribe` | Color-only flash |
| Showing a **correspondence** or mapping | `Shift` + optional dashed line | Instant jump |
| Extending an **existing idea** | `Stretch`, `scale` | Replace with larger version |
| Making something **temporarily stand out** | `ease_out_back` + scale pulse | Static highlight only |

### Using animation helpers

The `components.animation_helpers` module provides semantic animation functions that automatically bind the correct `rate_func` and `run_time` from the Motion=Meaning mapping above:

| To convey | Helper function | What it does internally |
|-----------|-----------------|----------------------|
| Introducing a **new concept** | `reveal(obj)` | `GrowFromCenter` + `ease_out_cubic` + auto run_time |
| A **derivation / step-by-step** process | `write_in(obj)` | `Write` + `linear` + auto run_time |
| Emphasizing a **key result** | `emphasize(obj)` | `Indicate` + `ease_out_back` + auto run_time |
| An **equivalence** or **transformation** | `transform_step(a, b)` | `ReplacementTransform` + `ease_in_out_sine` + auto run_time |
| Focal **circle highlight** | `highlight_circle(obj)` | `Circumscribe` + auto run_time |
| **Visual persistence** (shrink old to corner) | `shrink_to_corner(obj)` | `scale(0.45)` + `to_corner(DL)` |

Each helper returns the animation object so you can still override parameters if needed:
```python
self.play(reveal(new_concept), run_time=2.0)  # override default timing
```

Import: `from components.animation_helpers import reveal, write_in, emphasize, transform_step, shrink_to_corner`

### Rate function (easing) selection

The `rate_func` parameter controls how animation speed changes over time.
Manim provides 30+ functions; these are the ones that matter:

| Situation | Recommended rate_func | Why |
|-----------|----------------------|-----|
| **Reveals** (FadeIn, Create, Write) | `ease_out_cubic` or `ease_out_quad` | Fast start → gentle stop feels natural for appearance |
| **Transformations** (Transform, ReplacementTransform) | `ease_in_out_sine` or `smooth` | Both endpoints smooth; good for shape morphing |
| **Emphasis** (Indicate, Flash, Circumscribe) | `ease_out_back` or `ease_out_elastic` | Overshoot draws extra attention to the target |
| **Mechanical / linear motion** | `linear` | Constant speed = mechanical feel |
| **Default / unsure** | `smooth` | Sigmoid curve; never looks wrong |
| **Never use for reveals** | `ease_in_*` | Slow start makes appearance feel sluggish |

### Progressive reveal discipline

This is the single most important motion principle from professional math
animation (e.g. 3b1b style):

> **Never show the complete final state all at once.**
> **Each play() call should introduce or change at most 2–3 mobjects.**

Consequences:
- Split complex beats into multiple `self.play()` + `self.wait()` steps.
- If you find yourself passing 4+ mobjects to a single `play()`, split it.
- Use `LaggedStart(lag_ratio=0.15)` when elements should appear in a cascade
  (this counts as one orchestrated reveal, not N separate appearances).
- Use `Succession()` when one thing must finish before the next begins.

### Visual persistence mode

When a beat finishes, important visual information should **remain visible** in
a diminished form rather than disappearing:

- After a formula is transformed, **shrink the original** and move it to a
  corner (`to_corner(DL)` or `to_corner(DR)`) at `scale(0.45)`.
- This lets viewers glance back at earlier steps if they lose the thread.
- Only `FadeOut` truly temporary elements (highlight flashes, transition arrows).
- Never FadeOut the previous beat's main content — shrink-to-corner instead.

### Animation pacing vs narration

- Total animation duration per beat ≈ spoken narration length × 0.12–0.18 s/char
- A 10-character Chinese narration line (~3 seconds spoken) → 2.5–4 s of animation
- Animations shorter than narration feel rushed; longer feel dragging
- Use `self.wait(0.3–0.8)` after each reveal to let the viewer register what they saw
- **Avoid `self.wait(2.0)` or longer** — it makes viewers think the video froze

## Review checklist

- Does the opening show a real visual object quickly?
- Does each beat have a clear focal point?
- Are the important conclusions shown through visible change?
- Does the ending feel earned and connected to the opening?
- Is content distributed across screen zones (not everything crammed at center)?
- Are annotation labels placed in left/right zones, not overlapping the main content?
- Do element sizes follow hierarchy (main content > annotations > footnotes)?
