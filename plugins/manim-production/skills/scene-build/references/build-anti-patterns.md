# Build Anti-Patterns & Error Patterns

## Process anti-patterns

- Reordering beats without saying so
- Combining multiple planned beats into one overloaded frame
- Adding long text blocks that were not in the plan
- Using MathTex when the project guidance says to avoid LaTeX-heavy scenes
- Changing scene class or file naming without reason
- Dropping the takeaway frame from the plan

## Code anti-patterns

- Too much text on screen at once
- Mixing Chinese and English UI language without a deliberate reason
- Introducing several new formulas in one beat
- Large blocks of hard-coded coordinates for layout when relative positioning would work
- Narration that explains future steps before the viewer sees them
- End states with no clear conclusion frame or takeaway

---

# Common Build Errors and Fixes

This section covers predictable errors the AI encounters when writing Manim code,
their likely causes, and how to fix them.

## Rendering / LaTeX errors

| Error message | Cause | Fix |
|-------------|-------|-----|
| `LaTeXError: LaTeX command not found` | System has no LaTeX installation (MiKTeX, TeX Live) or dvisvgm missing | Use `Text()` instead of `Tex()`/`MathTex()` for non-math text; install MiKTeX if LaTeX is needed |
| `LaTeXError: latex error` (generic) | Invalid LaTeX syntax in `MathTex()`/`Tex()` | Check for unescaped special chars: `\` should be `\\`, `%` should be `\\%`; use raw strings: `r"\frac{a}{b}"` |
| `dvisvgm: command not found` | Missing SVG converter (part of LaTeX toolchain) | Install dvisvgm via your LaTeX distribution; or avoid `Tex()`/`MathTex()` |
| Output shows □□□ boxes | CJK characters inside `MathTex()` or `Tex()` | **Move CJK text to `Text()`**; keep formulas pure ASCII/LaTeX in `MathTex()` |

## Font errors

| Error message | Cause | Fix |
|-------------|-------|-----|
| `Font 'xxx' does not have a glyph for char 'x'` | Specified font doesn't contain the needed character | Remove explicit `font=` parameter (Pango auto-selects); or use `register_font()` first |
| `PangoWarning: ... cannot find font` | Font name misspelled or not installed | Use generic names like `"sans-serif"`, `"serif"`; check available fonts via `Text.font_list()` |
| Text renders as empty/invisible | Font size too small (`< 0.1`) or color matches background | Ensure `font_size >= 24` and color contrasts with background |

## Animation errors

| Error message | Cause | Fix |
|-------------|-------|-----|
| `Animation runtime exceeded` | Single animation `run_time` set extremely high (>30s) or updater loop doesn't terminate | Reduce `run_time`; add stop condition to updaters; check for infinite loops in custom animations |
| Object "jumps" instead of animating smoothly | Used `FadeIn`/`FadeOut` instead of continuous transform; or `run_time` too short (<0.3s) | Use `Transform`/`GrowFromCenter` for appearance; ensure `run_time >= 0.5` for any visible transition |
| Animation looks jerky / low framerate | `frame_rate` too low (e.g., 15fps in low quality) | Use `-qh` (high quality) for final render; `-qk` for preview is fine |
| Multiple objects animate but timing feels wrong | All given same `run_time` in one `play()` but have different natural durations | Use separate `play()` calls or `AnimationGroup` with individual timings |

## Layout errors

| Symptom | Cause | Fix |
|---------|-------|-----|
| `SurroundingRectangle` doesn't fully enclose object | Complex boundary (handwritten-style, irregular shape) | Add larger `buff=0.3–0.5`; switch to `BackgroundRectangle` which always covers full bounding box |
| Labels overlap despite using `next_to()` | Default `buff=0.25` too small for large objects | Increase buff to `MED_LARGE_BUFF=0.5`; or use `scale_to_fit_width()` to shrink labels |
| Object appears off-screen | Placed beyond frame boundaries (|x| > 7.1 or |y| > 4.0) | Call `.shift_onto_screen()` after positioning; or use relative placement (`to_edge()`) over hard coords |
| Everything clustered at center | Only used `move_to(ORIGIN)` for everything | Distribute across screen zones per `spatial-composition.md`; use `to_edge()`, `to_corner()` for secondary elements |
| Formula too large, crowds out labels | Default MathTex size too big for complex formula | Apply `.scale(0.7–0.85)`; or break into multiple smaller `MathTex` with `VGroup.arrange()` |

## Performance issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| First render very slow (10+ seconds) | No SVG cache; every Text/MathTex recompiles from scratch | This is normal on first run; subsequent runs of same scene use cache. Do NOT disable caching. |
| Render takes >5 minutes for a simple scene | Resolution too high for content complexity | Use `-ql` (low quality, 480p15fps) for iteration; `-qh` only for final output |
| Video file unexpectedly large (>50MB for <1 min) | High resolution + high fps + long duration + no compression | Reduce `frame_rate` via config; use `-qh` only when needed; shorter `wait()` times reduce static frames |
| Memory error during render | Too many detailed VMobjects on screen at once (thousands of points) | Simplify geometry; reduce graph sampling density; render in sections |

## Structural mistakes

| Mistake | Why it's wrong | Correct approach |
|---------|---------------|-----------------|
| `self.add(mob)` instead of `self.play(FadeIn(mob))` | Object appears instantly with no animation — jarring | Always introduce visual elements through `play()` unless intentionally instant |
| `self.remove(mob)` instead of `self.play(FadeOut(mob))` | Object vanishes instantly — viewer loses context | Use `FadeOut` for dismissal, or shrink-to-corner for persistence |
| No `self.wait()` between beats | Rushed pacing; viewer can't absorb each step | Add `self.wait(0.3–0.8)` after each meaningful play |
| `self.wait(3.0)` or longer | Viewer thinks video froze; wastes file size on static frames | Max `wait(1.5)`; prefer splitting into active sub-beats |
| One giant `construct()` with 200 lines | Unmaintainable; hard to debug specific beat | Split into helper methods: `_setup()`, `_show_step1()`, `_show_conclusion()` |
| Hard-coded coordinates everywhere | Fragile; breaks if anything moves | Use `next_to()`, `align_to()`, `to_edge()`, VGroup arrange methods |
| Copy-pasting same animation pattern 5+ times | Repetitive; hard to tune globally | Extract a helper method: `_reveal_with_label(mob, label_text)` |
