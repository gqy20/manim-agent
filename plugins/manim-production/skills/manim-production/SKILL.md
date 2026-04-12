---
name: manim-production
description: Produce, review, or refactor Manim scenes for educational videos with stronger scene structure, narration alignment, mathematical clarity, and render-time self-checks. Use when generating or improving Manim animation code, teaching demos, proof walkthroughs, function visualizations, or geometry scenes.
---

# Manim Production

Use this as the umbrella workflow router for Manim tasks.

## Primary job

- Route the task through the correct Manim production stages.
- Keep the stages in order: visible plan, build, narration alignment, render review.
- Use the specialized skills for the detailed rules instead of repeating them here.

## Required stage order

1. Use `scene-plan` first and emit a visible plan before coding.
2. Use `scene-build` only after that plan exists.
3. Apply `scene-direction` during planning and implementation to keep each beat visually strong.
4. Apply `layout-safety` on dense beats as an advisory audit before accepting the implementation.
5. Apply `narration-sync` before finalizing narration.
6. Use `render-review` after rendering and before reporting success.

## Skill routing

- `scene-plan`: beat structure, learning sequence, narration outline, build handoff
- `scene-build`: plan-to-code execution, render/debug loop, implementation refinement
- `scene-direction`: opening hook, focal hierarchy, motion-led explanation, ending payoff
- `layout-safety`: geometry-based advisory audits for overlap and frame-safety during implementation
- `narration-sync`: spoken pacing, beat-by-beat narration alignment, narration density control
- `render-review`: sampled-frame quality review and blocking issue detection

## Task classification

Choose one primary mode before building:

- `quick-demo`
- `concept-explainer`
- `proof-walkthrough`
- `function-visualization`
- `geometry-construction`

## Minimal checks

- Do not start `scene.py` before the visible plan exists.
- Do not skip the specialized skills when their phase is active.
- Prefer one `scene.py` file and one main `Scene` class unless the task truly needs more.
- If the first render fails, fix implementation problems before redesigning the lesson.

## References

- For scene flow, read `references/scene-patterns.md`.
- For narration quality, read `references/narration-guidelines.md`.
- For spatial composition (screen zones, sizing, color, per-mode layouts), read `references/spatial-composition.md`.
- For animation craft (motion selection, rate functions, timing, composition), read `references/animation-craft.md`.
- For layout or failure patterns, read only the specific reference you need.
