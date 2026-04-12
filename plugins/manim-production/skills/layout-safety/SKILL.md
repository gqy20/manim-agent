---
name: layout-safety
description: Audit Manim scene layouts for overlap, crowding, and frame overflow as an implementation-time advisory check. Use when arranging labels, formulas, callouts, braces, tables, or any dense beat where geometry-based layout checks can catch collisions earlier than frame review.
version: 1.0.0
argument-hint: " [layout-checkpoint-or-dense-beat]"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep]
---

# Layout Safety

Use this skill during implementation when a beat risks visual collisions.

## Why this exists

- Manim positioning helpers such as `next_to()` and `arrange()` use pairwise boundary alignment.
- They do not solve global layout or check third-party collisions for you.
- Dense math beats need an explicit geometry pass before render review.

## Primary goals

- Catch label, formula, arrow, and callout overlap before the final render pass.
- Keep important mobjects inside a safe frame margin.
- Turn layout concerns into concrete, measurable fixes instead of vague "less crowded" feedback.

## Audit workflow

1. Identify the densest beat or checkpoint in `construct()`.
2. The canonical helper implementation lives in `scripts/layout_safety.py` inside this skill.
3. Run the script directly with Python after `scene.py` exists.
4. Prefer `--checkpoint-mode after-play` so you catch crowded transient beats instead of only the final frame.
5. If the audit flags an issue, inspect it and adjust spacing, scaling, or beat structure when the warning reflects a real layout problem.
6. Remove temporary debugging scaffolds only after the layout is stable.

## Preferred command

```bash
python scripts/layout_safety.py scene.py GeneratedScene --checkpoint-mode after-play
```

Use `--checkpoint-mode final` only when you specifically want the ending frame.

## Expected output

- Exit code `0`: no layout issues found in the sampled checkpoints
- Exit code `1`: one or more overlap, crowding, or frame-overflow issues were found
- Exit code `2`: the audit script could not load or run the scene

Treat exit code `1` as a review signal, not as proof that the scene is unusable. Some mathematically meaningful layouts intentionally place labels, markers, or outlines inside the same local bounds.

## What to check

- Text, MathTex, and labels that sit beside the same focal object
- Braces, arrows, and captions that can intrude into formulas
- Tables, axes labels, and legends near frame edges
- Transition states where an old object has not fully left before a new one arrives

## Fix strategies

- Increase `buff` in `next_to()` or `arrange()`
- Reduce object width with `scale_to_fit_width()`
- Split one dense beat into two cleaner beats
- Move explanatory text to a different edge or corner
- Fade out or transform old emphasis objects before introducing new ones

## What to avoid

- Assuming `next_to()` prevents all collisions
- Only checking the final frame when the crowded state happens mid-beat
- Adding more highlight boxes or braces to an already dense composition
