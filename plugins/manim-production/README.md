# Manim Production Plugin

`manim-production` is a local Claude plugin for generating better educational Manim animations.

## Purpose

This plugin standardizes the workflow for planning, building, directing, and reviewing Manim scenes so generated videos are clearer, more teachable, and more visually coherent.

## Recommended workflow

1. `/scene-plan`
2. `/scene-build`
3. `/scene-direction`
4. `/narration-sync`
5. Final review with `manim-production`

## Included skills

- `manim-production`: umbrella workflow and quality guide
- `scene-plan`: beat-by-beat planning and build handoff
- `scene-build`: plan-to-code implementation and render refinement
- `scene-direction`: opening hook, focal hierarchy, motion-led explanation, and ending payoff
- `narration-sync`: spoken narration alignment and pacing

## Notes

- The plugin is designed to be used as a local plugin in this repository.
- The repository currently keeps both `.claude-plugin/` and `.codex-plugin/` manifests for compatibility.
- New Claude-facing integrations should prefer `.claude-plugin/`.
