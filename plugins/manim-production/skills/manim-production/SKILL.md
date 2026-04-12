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
7. Apply `intro-outro` after render-review when branded packaging is requested (optional).

## Skill routing

- `scene-plan`: beat structure, learning sequence, narration outline, build handoff
- `scene-build`: plan-to-code execution, render/debug loop, implementation refinement
- `scene-direction`: opening hook, focal hierarchy, motion-led explanation, ending payoff
- `layout-safety`: geometry-based advisory audits for overlap and frame-safety during implementation
- `narration-sync`: spoken pacing, beat-by-beat narration alignment, narration density control
- `render-review`: sampled-frame quality review and blocking issue detection
- `intro-outro`: branded intro/outro design, Revideo or Manim fallback, video concatenation contract

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
- If intro-outro is requested, emit `intro_spec` and/or `outro_spec` in structured output before finishing.

## Component Library

Reusable Python components in `components/` that encapsulate documented patterns into LLM-friendly APIs.

### Import pattern

```python
from components import (
    BUFFER, COLOR_PALETTE, TEXT_SIZES, SCREEN_ZONES,
    cjk_text, cjk_title, math_line, mixed_text, subtitle,
    TitleCard, EndingCard,
    ProofStepStack, FormulaTransform, StepLabel, StepKind,
    Callout, HighlightBox, LabelGroup,
    ZoneLayout, ModeLayout, SceneMode,
    reveal, write_in, emphasize, transform_step, shrink_to_corner, highlight_circle,
    TeachingScene,
)
```

Or import individually: `from components.text_helpers import cjk_text`

### Component quick reference

| What you need | Use this | Module |
|---------------|----------|--------|
| Style constants (buffers, colors, sizes) | `BUFFER.SMALL`, `COLOR_PALETTE.given`, `TEXT_SIZES.title` | `config.py` |
| Chinese text | `cjk_text("文本")`, `cjk_title("标题")` | `text_helpers.py` |
| Math formula | `math_line(r"a^2+b^2")` | `text_helpers.py` |
| Mixed CJK+math | `mixed_text("其中", r"x=2")` | `text_helpers.py` |
| Subtitle/caption | `subtitle("注释")` | `text_helpers.py` |
| Title card | `TitleCard.get_title_mobjects(title="...")` | `titles.py` |
| Ending card | `EndingCard.get_ending_mobjects(message="...")` | `titles.py` |
| Proof step stack | `ProofStepStack()` + `.add_step()` + `.build()` | `formula_display.py` |
| Formula transform | `FormulaTransform(original, target_latex)` | `formula_display.py` |
| Step labels | `StepLabel(StepKind.GIVEN)`, `StepLabel(StepKind.STEP, 1)` | `formula_display.py` |
| Corner callout | `Callout.create("已知", corner=UL)` | `annotations.py` |
| Highlight box | `HighlightBox.outline(target)`, `HighlightBox.filled(target)` | `annotations.py` |
| Vertex/angle/length labels | `LabelGroup()` + `.add_vertex()` + `.build()` | `annotations.py` |
| Zone-based layout | `ZoneLayout()` + `.set_title()` + `.build()` | `layouts.py` |
| Mode-based layout | `ModeLayout(SceneMode.PROOF_WALKTHROUGH)` | `layouts.py` |
| Semantic animations | `reveal()`, `write_in()`, `emphasize()`, `transform_step()` | `animation_helpers.py` |
| Shrink-to-corner | `shrink_to_corner(obj)` | `animation_helpers.py` |
| Teaching scene base class | `class MyScene(TeachingScene): ...` | `scene_templates.py` |

**Rule:** Always prefer component functions over raw Manim API calls for common patterns. Components enforce consistent styling, correct CJK handling, and proper animation timing automatically.

## References

- For scene flow, read `references/scene-patterns.md`.
- For narration quality, read `references/narration-guidelines.md`.
- For spatial composition (screen zones, sizing, color, per-mode layouts), read `references/spatial-composition.md`.
- For animation craft (motion selection, rate functions, timing, composition), read `references/animation-craft.md`.
- For render quality (presets, caching, performance, file size), read `references/render-quality.md`.
- For the 3Blue1Brown visual style profile (colors, typography, animation pacing, compositional patterns), read `references/style-3b1b.md`.
- For layout or failure patterns, read only the specific reference you need.
- For intro/outro templates and video assembly, read `../intro-outro/SKILL.md`.
