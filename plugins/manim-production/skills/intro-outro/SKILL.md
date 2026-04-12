---
name: intro-outro
description: Design and specify branded intro/outro segments for educational videos. Use when the task requires a title animation opening, branded outro frame, or full video assembly with intro + main content + outro. Advisory skill -- guides generation without blocking the core scene pipeline.
version: 1.0.0
argument-hint: " [intro-outro-config]"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep]
---

# Intro / Outro

Design and specify branded opening and closing segments for educational videos.

## Primary goals

- Produce a **3–5 second animated intro** that establishes visual identity before the main content.
- Produce a **3–5 second outro** that provides a takeaway or call-to-action after the main content.
- Keep both segments **template-driven** so they can be regenerated with different titles/messages.
- Ensure intro/outro **concatenate seamlessly** with the main Manim-rendered scene video.
- Support two generation backends:
  - **Revideo** (preferred): MIT-licensed TypeScript framework with headless rendering.
  - **Manim fallback**: Uses existing `TitleCard` / `EndingCard` components when Revideo is unavailable.

This is an **advisory skill** -- it does not block the core pipeline. If no intro/outro
is requested, the pipeline produces output identical to the current behavior.

## When this skill activates

Activate this skill when **any** of these conditions is true:

1. The user explicitly requests an intro, outro, "片头", "片尾", or "branded video".
2. The `--intro-outro` CLI flag is set on the pipeline invocation.
3. The task classification is `concept-explainer` and `target_duration >= 60`.
4. The user mentions branding, channel identity, subscribe reminder, or CTA.

If none of these conditions apply, **skip this skill entirely**.

## Intro template specification

When generating an intro, emit a structured spec in `structured_output.intro_spec`:

```yaml
title: string                     # Main title (e.g., "勾股定理")
subtitle: string | null           # Secondary line (e.g., "直角三角形三边关系")
brand_element: string | null      # Brand text/logo (e.g., channel name)
duration_seconds: float           # Target 3.0 - 5.0
animation_style: string           # One of the styles below
background_color: string          # Hex color, default "#050A14" (3b1b dark)
accent_color: string              # Hex color, default "#58C4DD" (3b1b blue)
music_cue: string | null           # Short sound description (e.g., "soft chime")
```

### Available intro styles

| Style ID | Visual effect | Mood | Best for |
|----------|---------------|------|----------|
| `fade_in_title` | Title fades in from black, subtitle slides up below | Clean, professional | Formal math topics |
| `write_title` | Title writes character-by-character like handwriting | Academic, thoughtful | Proofs, derivations |
| `reveal_from_center` | Title scales up from center with glow pulse | Dramatic, energetic | Key concepts, theorems |
| `typewriter` | Character-by-character reveal with cursor blink | Technical, modern | CS, algorithms |

### Intro timing guide

| Total duration | Title reveal | Subtitle/brand appear | Hold before transition |
|---------------|-------------|----------------------|----------------------|
| 3.0 s | 0.0–1.2 s | 1.0–2.0 s | 2.0–3.0 s |
| 4.0 s | 0.0–1.5 s | 1.2–2.5 s | 2.5–4.0 s |
| 5.0 s | 0.0–2.0 s | 1.5–3.5 s | 3.5–5.0 s |

## Outro template specification

When generating an outro, emit a structured spec in `structured_output.outro_spec`:

```yaml
message: string                   # Takeaway text (e.g., "记住：a² + b² = c²")
cta_text: string | null           # Call-to-action (e.g., "点赞关注，下期见")
subscribe_reminder: bool          # Show subscribe icon/text
duration_seconds: float           # Target 3.0 - 5.0
animation_style: string           # One of the styles below
background_color: string          # Hex color, default "#050A14"
accent_color: string              # Hex color, default "#83C167" (3b1b green)
```

### Available outro styles

| Style ID | Visual effect | Mood | Best for |
|----------|---------------|------|----------|
| `takeaway_card` | Centered message with subtle border glow | Conclusive, satisfying | Proof endings, key results |
| `cta_banner` | Bottom banner slides up with CTA + subscribe icon | Engaging, social | Channel growth focus |
| `minimal_fade` | Message fades in on dark background, holds, fades out | Calm, reflective | Summary takeaways |
| `qed_style` | Q.E.D. mark appears first, then takeaway message | Formal, academic | Proof walkthroughs |

### Outro timing guide

| Total duration | Message appear | CTA/extra appear | Hold before fade |
|---------------|----------------|-------------------|------------------|
| 3.0 s | 0.0–1.0 s | 1.0–2.0 s | 2.0–3.0 s |
| 4.0 s | 0.0–1.5 s | 1.2–2.8 s | 2.8–4.0 s |
| 5.0 s | 0.0–2.0 s | 1.5–3.5 s | 3.5–5.0 s |

## Revideo integration pattern

Revideo is the preferred backend for intro/outro generation. It is MIT-licensed,
TypeScript-based, and supports headless rendering via CLI.

### Project structure convention

Place Revideo template files under the task directory:

```
{task_dir}/
├── revideo/
│   ├── intro.tsx            # Intro template component
│   ├── intro-config.json    # Intro dynamic config
│   ├── outro.tsx            # Outro template component
│   └── outro-config.json    # Outro dynamic config
```

### Config JSON schema

Both `intro-config.json` and `outro-config.json` follow this shape:

```json
{
  "title": "勾股定理",
  "subtitle": "直角三角形三边关系",
  "brandElement": null,
  "duration": 4.0,
  "style": "fade_in_title",
  "backgroundColor": "#050A14",
  "accentColor": "#58C4DD",
  "resolution": { "width": 1920, "height": 1080 },
  "fps": 30
}
```

Outro config uses `message`, `ctaText`, `subscribeReminder` instead of title fields:

```json
{
  "message": "记住：a² + b² = c²",
  "ctaText": "点赞关注",
  "subscribeReminder": true,
  "duration": 4.0,
  "style": "takeaway_card",
  "backgroundColor": "#050A14",
  "accentColor": "#83C167",
  "resolution": { "width": 1920, "height": 1080 },
  "fps": 30
}
```

### Render command

```bash
# Render intro
npx revideo render {task_dir}/revideo/intro.tsx \
  --output {task_dir}/intro.mp4

# Render outro
npx revideo render {task_dir}/revideo/outro.tsx \
  --output {task_dir}/outro.mp4
```

### Template stub pattern

Each `.tsx` file should import config from its JSON sibling and use standard
Revideo primitives:

```tsx
import { FaDeIn, Rect, Txt, useVideoConfig } from "@revideo/2d";
import { useCurrentFrame, interpolate, spring } from "@revideo/core";
import config from "./intro-config.json";

export default makeScene2D("intro", function* (view) {
  // ... implementation based on config.style ...
});
```

For detailed API reference and complete template examples per style,
see `references/revideo-integration.md`.

### Resolution matching

**Critical**: All Revideo outputs must match the Manim render resolution:
- Width: **1920 px**
- Height: **1080 px**
- FPS: **30**

This matches Manim's `-qh` (1080p) default output. Mismatched resolutions
will cause concat failure or black bars.

## Manim fallback pattern

When Revideo is not installed or the user prefers pure Manim, generate intro/outro
as standalone Manim scenes using existing components.

### File placement

```
{task_dir}/
├── intro_scene.py             # Standalone intro scene
└── outro_scene.py             # Standalone outro scene
```

### Intro scene pattern

Use `TitleCard` as base class or extract mobjects via factory method:

```python
from components.titles import TitleCard

class IntroScene(TitleCard):
    title = "勾股定理"
    subtitle = "直角三角形三边关系"

    def construct(self):
        mobs = self.get_title_mobjects(
            title=self.title,
            subtitle=self.subtitle,
        )
        self.play(Write(mobs["title"]), run_time=1.5)
        if self.subtitle:
            self.play(FadeIn(mobs["subtitle"]), run_time=0.8)
        self.wait(1.0)
```

### Outro scene pattern

Use `EndingCard` as base class:

```python
from components.titles import EndingCard

class OutroScene(EndingCard):
    message = "记住：a² + b² = c²"
    show_qed = True

    def construct(self):
        mobs = self.get_ending_mobjects(
            message=self.message,
            show_qed=self.show_qed,
        )
        if self.show_qed:
            self.play(Write(mobs["qed"]), run_time=1.0)
            self.wait(0.3)
        self.play(FadeIn(mobs["message"]), run_time=1.0)
        self.wait(1.0)
```

### Render commands

```bash
# Render intro
manim -qh intro_scene.py IntroScene
# Output: media/videos/intro_scene.mp4

# Render outro
manim -qh outro_scene.py OutroScene
# Output: media/videos/outro_scene.mp4
```

### Duration control

To ensure 3–5 second output:
- Control `run_time` on each `self.play()` call explicitly.
- Limit total `self.wait()` to ≤ 1.5 seconds.
- Avoid long animations (`run_time > 2.0`) in intro/outro scenes.
- Verify output duration with `ffprobe` after rendering.

For detailed fallback templates per style, see `references/manim-fallback.md`.

## Structured output contract

When this skill is active, populate these fields in `PipelineOutput`:

| Field | Type | When to populate |
|-------|------|------------------|
| `intro_requested` | `bool` | Always set to `true` if intro was requested |
| `outro_requested` | `bool` | Always set to `true` if outro was requested |
| `intro_spec` | `dict` | When intro is requested (see Intro spec above) |
| `outro_spec` | `dict` | When outro is requested (see Outro spec above) |
| `intro_video_path` | `str` | Path to rendered intro MP4 (after successful render) |
| `outro_video_path` | `str` | Path to rendered outro MP4 (after successful render) |
| `intro_outro_backend` | `str` | `"revideo"` or `"manim"` |

If intro/outro was requested but rendering failed, set `_video_path` to `null`
and include error details in `deviations_from_plan`. Do not block pipeline completion.

## Concatenation contract

The backend pipeline calls `video_builder.concat_videos()` to assemble the final video:

```
[intro.mp4] + [main_content.mp4] + [outro.mp4] → final_output.mp4
```

Rules:
- All inputs must be **MP4**, same **1920x1080** resolution, same **30 fps**.
- Order is always: intro → main → outro.
- Missing segments are simply omitted (e.g., only intro + main).
- Concatenation uses FFmpeg **stream copy** (`-c copy`) — no re-encoding, lossless.
- The concatenated output **overwrites** the original `final_video_output` path.
- Audio tracks from intro/outro are preserved (e.g., music cue in intro).

## Review checklist

After generating intro/outro segments, verify:

- [ ] Intro duration is between 3–5 seconds (check with ffprobe).
- [ ] Outro duration is between 3–5 seconds.
- [ ] Colors match the palette defined in `references/style-3b1b.md`.
- [ ] Resolution is 1920x1080 @ 30fps (matches main scene).
- [ ] Text is readable at target resolution (no tiny fonts).
- [ ] CTA text (if present) matches the target audience language.
- [ ] No abrupt cuts between segments — transitions feel natural.
- [ ] `intro_spec` / `outro_spec` are populated in structured output.
- [ ] `intro_video_path` / `outro_video_path` point to existing files.

## References

- For Revideo integration patterns, CLI usage, and API reference, read `references/revideo-integration.md`.
- For intro template catalog with visual specs and code sketches, read `references/intro-templates.md`.
- For outro template catalog with visual specs and code sketches, read `references/outro-templates.md`.
- For pure-Manim fallback approach with complete scene templates, read `references/manim-fallback.md`.
- For the 3Blue1Brown visual style profile (colors, pacing), read `../manim-production/references/style-3b1b.md`.
