---
name: render-review
description: Review rendered Manim video frames before a task is allowed to succeed. Uses AI vision analysis to inspect sampled frames for opening clarity, beat focus, visual density, conclusion payoff, or other blocking visual issues after rendering.
version: 1.0.1
argument-hint: " [rendered-video-or-frame-set]"
allowed-tools: [Read, Glob, Grep]
vision-enabled: true
---

# Render Review

Use this skill after rendering and before reporting success.

## Primary goals

- Catch blocking visual issues from the actual rendered output, not just from the code.
- Check that the opening, middle beats, and ending all look intentional.
- Reject renders that are technically complete but visually weak or misleading.
- Perform **per-frame visual analysis** using AI vision to ground review decisions in actual pixel content.

## Review workflow

1. **MUST read every frame image** using the Read tool — this is not optional.
2. For each frame, form a concrete visual assessment using the criteria below.
3. Compare assessments against the intended scene structure if a plan is available.
4. Decide whether the render is acceptable or must be revised.
5. If revision is needed, explain the blocking issues concretely enough for the next build pass.

## Per-frame assessment

For each sampled frame, report:

| Dimension | What to check |
|-----------|---------------|
| **On-screen content** | What objects, text, formulas, labels, arrows are visible? |
| **Visual density** | sparse / balanced / crowded |
| **Focal point** | Is there one clear main subject? |
| **Label readability** | clear / partially obscured / illegible / none present |
| **Visual issues** | overlap, cutoff, too small, wrong position, etc. |

Each frame is labeled with its beat context (e.g. `opening`, `beat_2__Core formula`, `ending`). Use this label to cross-reference against what that beat was supposed to show.

## Blocking issues

Mark the render as blocked if any of these are true:

- The opening frame is mostly empty or title-only with no meaningful visual object.
- A key beat looks overcrowded or visually confusing.
- An important conclusion is stated but not shown through visible change.
- The ending lacks a clear takeaway or does not resolve the opening question.
- Labels, formulas, or focal objects compete so strongly that the main idea is unclear.
- Vision analysis reports `illegible` labels on a frame that should show readable content.

## Pipeline handoff

When this skill is used in the main pipeline, return the review through the
runtime-provided structured output schema. Do not redefine the schema in this
skill.

The handoff should make these facts clear:

- Whether the render is acceptable.
- What visual evidence supports the decision.
- Which sampled frames were inspected.
- Which issues are blocking versus optional suggestions.
- What the next build pass should change if revision is needed.

## What to avoid

- Passing a render just because the file exists.
- Skipping frame image reading — you MUST visually inspect each frame.
- Reporting vague feedback like "make it better" without a concrete symptom.
- Treating a minor style preference as a blocking issue.
- Contradicting what the vision analysis shows without evidence from the frame itself.
