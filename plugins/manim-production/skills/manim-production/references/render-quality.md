# Render Quality & Performance Guide

This reference covers how to configure Manim's rendering pipeline for optimal
output quality, fast iteration, and reasonable file sizes.

## Quality Presets

Manim provides four quality levels, selectable via `-q` flag or `config.quality`.

| Preset | Flag | Resolution | Frame rate | Pixel count | Use case |
|--------|------|-----------|------------|-------------|---------|
| **low** | `-ql` | 854×480 | 15 fps | ~410K | Quick previews, rough drafts |
| **medium** | `-qm` | 1280×720 | 30 fps | ~922K | Iteration, testing |
| **high** (default) | `-qh` | 1920×1080 | 60 fps | ~2.07M | Final output |
| **fourk** | `-qk` | 3840×2160 | 60 fps | ~8.29M | Presentation / 4K display |

### How to choose

```
During development (iteration loop):
  → -qm (medium) — fast enough to iterate in <30s
  → Accept slightly lower visual quality for speed

For final render:
  → -qh (high) — standard production quality
  → Only use -qk if target platform is specifically 4K

Never use -ql for final output visible to users.
```

## Caching System

Manim caches rendered mobjects to avoid redundant re-rendering. Understanding
this is critical for predicting render times.

### What gets cached

| Mobject type | Cached? | Cache key | First render | Subsequent |
|-------------|--------|-----------|-------------|-----------|
| `Text()` (Pango) | Yes | Content string + font/size/color | Slow (Pango layout) | Near-instant |
| `MathTex()` / `Tex()` (LaTeX) | Yes | LaTeX source + template | Very slow (LaTeX compile) | Near-instant |
| SVG-based shapes (`SVGMobject`) | Yes | SVG content | Slow (SVG parse) | Near-instant |
| `Circle`, `Square`, `Line` etc. | No (lightweight) | N/A | Fast every time | Same speed |
| Composites (`VGroup`) | Depends on children | — | Sum of children | — |

### Practical implications

**First render of a scene is always slower** because:
1. LaTeX must be invoked for each unique `MathTex`/`Tex()` expression
2. Pango must lay out each unique `Text()` string
3. No partial movie cache exists yet

**Second+ renders of the same scene are much faster** because:
1. SVG cache hits for all text/formula mobjects
2. Partial movie files may be reused if only later beats changed
3. Manim's incremental rendering skips unchanged animations

**Do NOT disable caching** (`--disable_caching`). It exists only for debugging
specific cache-related bugs. Disabling it makes every render as slow as the first.

## File Size Budgeting

Output video size depends on: resolution × frame_rate × duration × compression.

### Estimated file sizes (H.264/AVC)

| Duration | -qh (1080p60) | -qm (720p30) | -ql (480p15) |
|---------|---------------|---------------|---------------|
| 10 seconds | ~3–6 MB | ~0.8–1.5 MB | ~0.2–0.5 MB |
| 30 seconds | ~8–15 MB | ~2–4 MB | ~0.5–1.2 MB |
| 60 seconds | ~15–30 MB | ~4–8 MB | ~1–2.5 MB |
| 120 seconds | ~30–60 MB | ~8–16 MB | ~2–5 MB |

### Ways to reduce file size

| Technique | Impact | Trade-off |
|-----------|--------|----------|
| Lower frame rate (-qm vs -qh) | ~50% smaller | Less smooth motion |
| Shorter wait() times | Fewer static frames | Slightly faster pacing |
| Remove unnecessary FadeOut/FadeIn pairs | Fewer transition frames | Slightly more abrupt cuts |
| Reduce resolution for simple scenes | Proportional size drop | Softer edges on complex content |
| Use `-y` (ffmpeg) with higher CRF | Better compression | Slightly longer encode |

## Renderer Backends

Manim supports two rendering backends:

### Cairo (default)

- **Pros**: Mature, reliable, exact pixel output, full feature support
- **Cons**: CPU-only, slower for complex scenes, no GPU acceleration
- **Best for**: Text-heavy scenes, precise typography, final output

### OpenGL (`-gl`)

- **Pros**: GPU-accelerated, 5–10× faster for vector-heavy scenes
- **Cons**: Some mobjects not fully supported, visual differences possible,
  requires compatible GPU drivers
- **Best for**: Scenes with many geometric shapes, curves, 3D objects;
  rapid iteration when available

```bash
# Use OpenGL renderer
manim -pql scene.py        # low quality + OpenGL
manim -pqh --gl scene.py   # high quality + OpenGL
```

**Recommendation**: Try `-gl` during development if your GPU supports it.
Switch to Cairo (default) for final render if you notice visual artifacts.

## Common Performance Bottlenecks

Bottleneck 1: Too many unique MathTex expressions
→ Each unique LaTeX string triggers a separate compilation. Consolidate
  repeated formulas into one `MathTex` and `.copy()` it.

Bottleneck 2: Excessive point counts in parametric functions
→ `axes.plot(lambda x: f(x), use_smoothing=True)` can generate thousands of points.
  Reduce sampling density: `n_samples=50` or similar.

Bottleneck 3: High-resolution background images
→ Large `ImageMobject` or `SVGMobject` from complex SVGs consume memory.
  Scale down or simplify.

Bottleneck 4: Long static waits
→ `self.wait(5.0)` at 60fps = 300 frames of identical pixels.
  Replace with shorter waits or active "breathing" animation (subtle pulse).

Bottleneck 5: Full-scene re-renders during iteration
→ If you change beat 4 of 5, Manim still re-renders beats 1–3 from scratch
  (thanks to partial movies, but text/formula cache helps here).
  Structure code so beats are independent methods; test individual beats.

## Rendering Command Reference

```bash
# Basic render (uses default quality = high)
manim -pqlh scene.py

# With specific quality
manim -qm scene.py          # medium (fast iteration)
manim -qh scene.py          # high (final output)
manim -qk scene.py          # 4K (presentation)

# With OpenGL backend
manim -pqlh --gl scene.py

# Render only a range of frames (useful for testing middle of scene)
manim -pqlh -s 200 -e 300 scene.py   # Frames 200–300 only

# Output to custom location
manim -pqlh --media_dir=output/scene.py

# Show file write locations (dry run, no actual render)
manim -pqlh --dry_run scene.py
```

## Quality Checklist Before Final Render

Run through this before committing to `-qh` final output:

- [ ] All Chinese text uses `Text()`, not `Tex()`/`MathTex()`
- [ ] All `wait()` calls are ≤ 1.5s (prefer ≤ 0.8s)
- [ ] Total `play()` run_time sums to target duration ± 20%
- [ ] No hard-coded coordinates that might break on resize
- [ ] Scene tested at least once at `-qm` for timing verification
- [ ] Background color is intentional (not default black by accident)
- [ ] Font sizes are ≥ 24 for readability at 1080p
- [ ] No orphaned mobjects (added but never animated or removed)
