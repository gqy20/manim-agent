---
name: manim-production
description: Produce, review, or refactor Manim scenes for educational videos with stronger scene structure, narration alignment, mathematical clarity, and render-time self-checks. Use when generating or improving Manim animation code, teaching demos, proof walkthroughs, function visualizations, or geometry scenes.
---

# Manim Production

Follow this workflow when working on a Manim task.

## Recommended full flow

- Use `/scene-plan` first for most educational, proof, concept, function, or geometry tasks.
- Use `/scene-build` after a plan exists and implementation should follow that plan.
- Use `/scene-direction` to enforce stronger opening beats, visual focus, motion-led explanation, and ending payoff.
- Use `/narration-sync` to keep spoken narration aligned to the current beat and visual timing.
- Use this `manim-production` skill as the umbrella quality guide across all steps.
- Skip `/scene-plan` only for genuinely tiny one-beat demos.

## Classify the task

Choose one primary mode before writing code:

- `quick-demo`: very small visual proof-of-life or simple transition
- `concept-explainer`: introduce an idea step by step
- `proof-walkthrough`: show assumptions, transformations, then conclusion
- `function-visualization`: graph behavior, parameters, or geometric meaning
- `geometry-construction`: build shapes, marks, and relationships in order

## Read only the references you need

- For overall scene flow, read `references/scene-patterns.md`.
- For spoken script quality, read `references/narration-guidelines.md`.
- For layout, formulas, axes, and emphasis, read `references/math-visualization-guidelines.md`.
- For implementation style, read `references/code-style.md`.
- For common failure cases, read `references/anti-patterns.md`.

## Skill responsibilities

- `/scene-plan`: beat structure, learning sequence, narration outline, and build handoff
- `/scene-build`: plan-to-code execution, render/debug loop, and implementation refinement
- `/scene-direction`: opening hook, per-beat visual focus, motion-first explanation, and ending payoff
- `/narration-sync`: spoken pacing, beat-by-beat narration alignment, and narration density control

## Plan before coding

- Keep one main learning objective per scene.
- Prefer one scene file and one main `Scene` class unless the task truly needs more.
- Decide the visual sequence first: setup, reveal, transform, takeaway.
- Keep each beat focused on one new idea.
- Ensure the opening beat introduces both the topic and a visible object, not a title card alone.
- Ensure every important conclusion is shown through a visible change, not just stated as text.

## Check before rendering

- Confirm the file path and class name match the task requirements.
- Confirm the screen is not overloaded with text.
- Confirm narration describes what the viewer is seeing now, not future steps.
- Confirm colors, labels, and emphasis are consistent.
- Confirm there is a clear ending state or takeaway frame.
- Confirm each beat has one primary focal object or formula.
- Confirm the ending frame clearly resolves the question introduced at the start.

## If the first render fails

- Fix path, class name, or command issues before redesigning the animation.
- Fix syntax, import, or object-construction issues before changing pedagogy.
- If the render succeeds but the result is crowded or confusing, simplify the scene instead of adding more text.
