# Manim Production Plugin

`manim-production` is a local Claude plugin for generating better educational Manim animations.

## Purpose

This plugin standardizes the workflow for planning, building, directing, and reviewing Manim scenes so generated videos are clearer, more teachable, and more visually coherent.

## Recommended workflow

1. `/scene-plan`
2. `/scene-build`
3. `/scene-direction`
4. `/layout-safety`
5. `/narration-sync`
6. `/render-review`
7. Final pass under `manim-production`

These labels are stage names and skill entry points. The runtime may require the skills implicitly even when the model does not literally type each slash command.

## Included skills

- `manim-production`: umbrella workflow and quality guide
- `scene-plan`: beat-by-beat planning and build handoff
- `scene-build`: plan-to-code implementation and render refinement
- `scene-direction`: opening hook, focal hierarchy, motion-led explanation, and ending payoff
- `layout-safety`: geometry-based advisory checks for overlap, crowding, and frame overflow on dense beats
- `narration-sync`: spoken narration alignment and pacing
- `render-review`: sampled-frame review and blocking issue detection before success

## Runtime gates

The backend enforces pipeline contracts in runtime code instead of relying on
skill text as the source of truth:

- Phase 1 must return the dedicated `phase1_planning` structured output.
- Phase 2 must return the dedicated `phase2_implementation` structured output.
- Phase 2 validates real render artifacts before later phases continue.
- Render review and duration checks run after implementation acceptance.

Skills should describe workflow and quality criteria. They should not redefine
the pipeline output schema. The current schema contracts live in runtime code
and `docs/phase/`.

`layout-safety` is intentionally not a hard backend gate. It is an implementation-time review aid for crowded compositions, and its warnings should be interpreted with visual judgment rather than treated as automatic failures.

## Notes

- The plugin is designed to be used as a local plugin in this repository.
- The repository currently keeps both `.claude-plugin/` and `.codex-plugin/` manifests for compatibility.
- New Claude-facing integrations should prefer `.claude-plugin/`.
