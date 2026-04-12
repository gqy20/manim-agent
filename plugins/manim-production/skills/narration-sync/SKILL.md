---
name: narration-sync
description: Keep narration spoken, beat-aligned, and visually synchronized for Manim teaching animations. Use when writing, reviewing, or refining narration so it matches the current visual beat instead of sounding like a detached summary.
version: 1.0.0
argument-hint: " [narration-or-plan]"
allowed-tools: [Read, Glob, Grep]
---

# Narration Sync

Use this skill to keep voice-over aligned with what the viewer is seeing now.

## Primary goals

- Make narration sound spoken, not like slide bullets.
- Align narration to beats, not code blocks.
- Keep narration focused on the current visual action.
- Cover the full animation flow without collapsing into a one-sentence summary.

## Narration rules

- Write one or two spoken sentences per beat by default.
- Describe what is currently appearing, moving, changing, or being compared.
- Avoid pre-explaining future steps before the visuals arrive.
- Avoid long stacked clauses when one short sentence would do.
- If the canvas is already dense, make the narration simpler instead of adding more text.

## Alignment rules

- Each beat should have a corresponding narration segment.
- Narration should land on the same order as the visual beats.
- If the scene changes order during implementation, update the narration to match.
- If a beat is mostly visual, use a shorter narration line instead of filling the silence with extra explanation.

## What to avoid

- One sentence that summarizes the whole animation.
- Narration that reads like a proof transcript instead of speech.
- Narration that introduces terms not yet visible on screen.
- Narration that repeats the exact on-screen text without adding guidance.

## Review checklist

- Can each narration line be mapped to a specific beat?
- Does the narration describe the current visual state instead of future steps?
- Is the spoken rhythm short enough to sound natural?
- Does the narration cover the whole animation from opening to ending?
