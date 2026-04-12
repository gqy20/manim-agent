---
name: render-review
description: Review rendered Manim video frames before a task is allowed to succeed. Use when inspecting sampled frames for opening clarity, beat focus, visual density, conclusion payoff, or other blocking visual issues after rendering.
version: 1.0.0
argument-hint: " [rendered-video-or-frame-set]"
allowed-tools: [Read, Glob, Grep]
---

# Render Review

Use this skill after rendering and before reporting success.

## Primary goals

- Catch blocking visual issues from the actual rendered output, not just from the code.
- Check that the opening, middle beats, and ending all look intentional.
- Reject renders that are technically complete but visually weak or misleading.

## Review workflow

1. Inspect the sampled review frames.
2. Compare them against the intended scene structure if a plan is available.
3. Decide whether the render is acceptable or must be revised.
4. If revision is needed, explain the blocking issues concretely enough for the next build pass.

## Blocking issues

Mark the render as blocked if any of these are true:

- The opening frames are mostly empty or title-only with no meaningful visual object.
- A key beat looks overcrowded or visually confusing.
- An important conclusion is stated but not shown through visible change.
- The ending lacks a clear takeaway or does not resolve the opening question.
- Labels, formulas, or focal objects compete so strongly that the main idea is unclear.

## Review output

- Return a short summary.
- Return `approved: false` if any blocking issue is present.
- List each blocking issue as a concise standalone item.
- Add concrete suggested edits that tell the next build pass what to change.

## What to avoid

- Passing a render just because the file exists.
- Reporting vague feedback like "make it better" without a concrete symptom.
- Treating a minor style preference as a blocking issue.
