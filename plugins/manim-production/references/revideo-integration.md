# Revideo Integration Guide

## What is Revideo

Revideo is an **MIT-licensed** open-source framework for programmatic video editing.
It is forked from Motion Canvas (18K+ stars) and redesigned as a **library** that can be
embedded into applications, with headless rendering support.

- **License**: MIT (free for any use, including commercial)
- **Language**: TypeScript / JSX
- **Stars**: 3,753 (GitHub: redotvideo/revideo)
- **Docs**: https://docs.re.video
- **Repo**: https://github.com/redotvideo/revideo

## Why Revideo over Remotion for this project

| Feature | Revideo | Remotion |
|---------|---------|----------|
| License | MIT (unrestricted) | Free for ≤3 people; paid for 4+ |
| Headless rendering | Built-in API + CLI | Available (paid tier more complete) |
| Parallel rendering | Supported | Limited |
| Audio support | `<Audio/>` tag native | Via `<Audio/>` or static file |
| Cloud deployment | Official GCF example | Via Lambda |
| Community size | Smaller (~3.7K stars) | Larger (~28K stars) |
| Activity | Last update May 2025 | Actively maintained |

## Installation

### Quick start (per-task)

```bash
# In the task directory, initialize a minimal Revideo project
cd {task_dir}/revideo
npm init -y
npm install @revideo/core @revideo/cli @revideo/2d @revideo/renderer @revideo/ffmpeg
```

### Global install (alternative)

```bash
npm install -g @revideo/cli
```

## Project structure

A minimal Revideo project for intro/outro generation:

```
{task_dir}/revideo/
├── package.json
├── tsconfig.json
├── intro.tsx              # Intro scene component
├── intro-config.json      # Intro dynamic parameters
├── outro.tsx              # Outro scene component
└── outro-config.json      # Outro dynamic parameters
```

### package.json

```json
{
  "name": "intro-outro-templates",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "render-intro": "revideo render intro.tsx --output ../intro.mp4",
    "render-outro": "revideo render outro.tsx --output ../outro.mp4"
  },
  "dependencies": {
    "@revideo/core": "^0.10.0",
    "@revideo/2d": "^0.10.0",
    "@revideo/cli": "^0.10.0"
  }
}
```

### tsconfig.json

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "resolveJsonModule": true
  }
}
```

## CLI render command

```bash
# Basic render
npx revideo render src.tsx --output output.mp4

# With custom config override (overrides useVideoConfig defaults)
npx revideo render intro.tsx --output ../intro.mp4

# Render only specific frames (for debugging)
npx revideo render intro.tsx --frames 0-90 --output debug.mp4
```

Output goes to the specified `--output` path as an MP4 file.

## Core API reference

### Scene definition

```tsx
import { makeScene2D } from "@revideo/2d";

export default makeScene2D("scene-name", function* (view) {
  // Generator function — each yield is a frame boundary
  // Use view.add() to add elements
  // Use yield* for animations that span multiple frames
});
```

### Essential imports

```tsx
// Layout and primitives
import { Rect, Circle, Txt, Img, Video, Audio } from "@revideo/2d";

// Animation functions
import { FaDeIn, FadeIn, FadeOut, Create, Write, slideIn, scaleIn } from "@revideo/2d";

// Core utilities
import {
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  linear,
  waitFor,
  chain,
  all,
  loop,
} from "@revideo/core";
```

### Common patterns

#### Text display

```tsx
<Txt fill="white" fontSize={60} fontFamily="sans-serif">
  {config.title}
</Txt>
```

#### Colored rectangle (background)

```<Rect
  width={1920}
  height={1080}
  fill={config.backgroundColor || "#050A14"}
/>
```

#### Fade-in animation

```tsx
const title = (
  <Txt fill="white" fontSize={60}>
    {config.title}
  </Txt>
);
yield* view.add(<FaDeIn duration={30}>{title}</FaDeIn>);
```

#### Spring-based scale animation

```tsx
const logo = createRef<Txt>();
view.add(
  <Txt ref={logo} fill={config.accentColor} fontSize={80}>
    Logo
  </Txt>
);
yield* logo().scale(spring({ to: 1.2, from: 0, config: { damping: 12 } }), 40);
yield* logo().scale(spring({ to: 1.0, from: 1.2, config: { damping: 12 } }), 20);
```

#### Interpolated position

```tsx
const frame = useCurrentFrame();
const { fps } = useVideoConfig();
const yPosition = interpolate(frame, [0, 30], [-200, 0], { extrapolateRight: "clamp" });
// Apply to element via y() prop or style transform
```

### Config-driven pattern

Read dynamic values from a JSON config file:

```typescript
import config from "./intro-config.json";

// In the scene:
const bgColor = config.backgroundColor || "#050A14";
const accentColor = config.accentColor || "#58C4DD";
const duration = config.duration || 4.0;
```

This allows the LLM to generate the JSON config separately from the template code,
making it easy to regenerate intros/outros with different titles without touching TSX.

## Resolution matching

**All Revideo outputs must match Manim's default render settings:**

| Property | Value |
|----------|-------|
| Width | 1920 px |
| Height | 1080 px |
| FPS | 30 |
| Codec | H.264 (default) |

Set in `useVideoConfig()` or pass via CLI:

```tsx
// In template:
import { useVideoConfig } from "@revideo/core";

const { width, height, fps } = useVideoConfig();
// Default: 1920x1080@30fps — matches Manim -qh
```

If resolution mismatch occurs, re-encode with FFmpeg before concat:

```bash
ffmpeg -i input.mp4 -vf scale=1920:1080 -r 30 -c:v libx264 output.mp4
```

## Audio handling

### Background music cue in intro

```tsx
import { Audio } from "@revideo/2d";

view.add(
  <Audio
    src="chime.mp3"
    play={true}
    time={0}
  />
);
```

### Audio file placement

Put audio assets alongside templates:

```
{task_dir}/revideo/
├── assets/
│   └── chime.mp3          # Short sound effect for intro
├── intro.tsx
└── intro-config.json
```

Reference audio files using relative paths from the template location.

## Error recovery

| Error | Cause | Recovery |
|-------|-------|----------|
| `command not found: npx` | Node.js not installed | Fall back to Manim backend |
| `revideo render` fails | Missing dependency or TS error | Check `npm install` output; fall back to Manim |
| Output resolution mismatch | Config not set correctly | Re-encode with FFmpeg before concat |
| Render timeout (>60s) | Complex animation or slow machine | Simplify template or reduce duration |
| Empty/corrupt MP4 | Renderer crash | Delete output, retry, or fall back to Manim |

When falling back to Manim, set `intro_outro_backend: "manim"` in structured output
and note the fallback reason in `deviations_from_plan`.
