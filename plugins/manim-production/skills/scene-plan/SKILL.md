---
name: scene-plan
description: Create a scene plan before writing Manim code. Use when the task needs beat-by-beat planning, scene segmentation, narration outline, pacing decisions, or visual teaching structure before implementation. Trigger for requests like "plan the animation", "split this into scenes", "design the storyboard", "how should this Manim lesson be structured", or before building a teaching animation that needs stronger structure.
version: 1.0.0
argument-hint: " [topic-or-goal]"
allowed-tools: [Read, Glob, Grep]
---

# Scene Plan

Produce a compact plan for the animation before code is written.

## Output format

Return a plain Markdown plan with these sections in order:

1. `Mode`
2. `Learning Goal`
3. `Audience`
4. `Beat List`
5. `Narration Outline`
6. `Visual Risks`
7. `Build Handoff`

## Beat List rules

- Use 3 to 6 beats by default.
- Give each beat a short title.
- Give each beat exactly one new teaching point.
- For each beat include:
  - `Goal`
  - `Visuals`
  - `Key motion`
  - `Max duration`

## Narration rules

- Map narration to beats, not to code blocks.
- Keep narration spoken and natural.
- Prefer one or two sentences per beat.
- Do not write the full final voice-over script unless the user asks.

## Planning heuristics

- Start with the object, question, or formula.
- Build setup before explanation.
- Show one relationship at a time.
- End with a takeaway frame.
- If the task is mathematical, prefer visual progression over text density.

## Use references only when needed

All reference files are under `<plugin_dir>/references/`. Paths below are
relative to the plugin root directory.

- For beat templates, read `references/beat-patterns.md`.
- For plan shape, read `references/scene-plan-template.md`.
- For failure patterns, read `references/planning-anti-patterns.md`.
- For spatial planning in each beat's Visuals field (screen zones, element positions, sizing), read `references/spatial-composition.md`.

## Build handoff

End with a short `Build Handoff` section that tells the implementation step:

- the recommended file name
- the recommended main scene class name
- the intended scene flow in one line
- any constraints such as "avoid MathTex" or "keep all labels on screen"
- **recommended components** from `components/` library (e.g., "use `ProofStepStack` for derivation beats", "use `TeachingScene` as base class", "use `ZoneLayout` for screen zoning")
- `Skill Signature: mp-scene-plan-v1`

### Component selection guide for Build Handoff

When writing the Build Handoff, suggest components based on scene mode:

| Scene mode | Recommended components |
|-----------|----------------------|
| `proof-walkthrough` | `ProofStepStack`, `StepLabel`, `StepKind`, `FormulaTransform`, `TeachingScene` |
| `geometry-construction` | `LabelGroup`, `HighlightBox`, `Callout`, `ZoneLayout`, `mixed_text` |
| `function-visualization` | `cjk_title`, `math_line`, `Callout`, `ZoneLayout` |
| `concept-explainer` | `TitleCard`, `EndingCard`, `reveal`, `emphasize`, `shrink_to_corner` |
| `quick-demo` | `cjk_text`, `math_line`, `write_in`, basic layout |
