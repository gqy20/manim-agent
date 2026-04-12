---
name: scene-build
description: Build a Manim scene from an existing scene plan. Use when a beat-by-beat plan already exists and the next step is to implement, render, and refine the animation code. Trigger for requests like "build from this plan", "implement this storyboard", "turn this scene plan into Manim", or after running /scene-plan.
version: 1.0.0
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
5. Render, inspect, and simplify if the result feels crowded.

## Beat-to-code mapping

- Each beat should correspond to one visible stage in `construct()`.
- Prefer comments that mark beat boundaries.
- Keep each beat focused on one reveal, transform, or emphasis change.
- Keep narration aligned to the current beat.

## Quality checks

- Confirm the code matches the planned beat order.
- Confirm labels stay near the objects they describe.
- Confirm there is a clear ending frame.
- Confirm the final narration covers all beats in order.

## Use references only when needed

- For code style and render hygiene, read `../manim-production/references/code-style.md`.
- For math layout and emphasis, read `../manim-production/references/math-visualization-guidelines.md`.
- For common implementation mistakes, read `references/build-anti-patterns.md`.

## Final response

Include:

- what was built
- whether the render succeeded
- any deviation from the original scene plan
- the final scene class name
- `implemented_beats`: the beat titles actually implemented, in order
- `build_summary`: one short summary of what the build phase delivered
- `deviations_from_plan`: an explicit list, even if empty
