# Code Style

- Prefer clear object names over anonymous chained expressions.
- Extract repeated coordinates or colors into named variables.
- Prefer Manim relationships like `next_to`, `align_to`, `to_edge`, and groups over excessive hard-coded screen coordinates.
- Use `VGroup` to manage related elements.
- Keep animation order readable. The code should show the teaching sequence.
- Add a brief comment only when the visual logic would otherwise be hard to parse.

## Construct-to-Frame Mapping

Understanding how `construct()` code maps to rendered video frames is essential
for making informed decisions about timing and file size.

### How frames are generated

Manim's renderer captures frames at a fixed `frame_rate` (frames per second).
Each `self.play()` call generates a sequence of frames; `self.wait()` generates static
frames; `self.add()` / `self.remove()` take effect instantly (0 frames).

```
Code                                    →  Frames generated (at 60fps)
─────────────────────────────────────────────────────────────
self.play(FadeIn(a), run_time=1.0)        →  ~60 frames (fade 0%→100%)
self.wait(0.5)                             →  ~30 frames (static image)
self.play(Transform(a, b), run_time=2.0)    →  ~120 frames (morph)
self.wait(0.3)                             →  ~18 frames (static)
self.play(Indicate(b), run_time=0.8)        →  ~48 frames (flash + settle)
self.remove(a)                             →   0 frames (instant gone)
```

### Key implications

| Code pattern | Frame cost | Video impact |
|-------------|-----------|-------------|
| `self.play(..., run_time=T)` | **T × fps** frames | Directly determines video duration and file size |
| `self.wait(T)` | **T × fps** static frames | Adds duration but no motion; inflates file size |
| `self.add(mob)` | 0 frames | Free — but jarring if viewer expects animation |
| `self.remove(mob)` | 0 frames | Free — but jarring if viewer expects fade-out |
| `self.play(Succession(a, b))` | sum of individual run_times | Sequential = longer total |
| `self.play(LaggedStart(*mobs))` | max run_time + overlaps | Cascaded feel with moderate frame cost |

### Practical rules derived from mapping

1. **`run_time` is the primary lever for video length** — every second of `run_time`
   at 60fps = 60 frames ≈ 2–4 KB in output.  Choose the minimum `run_time` that
   looks good.

2. **`wait()` is not free** — `self.wait(2.0)` at 60fps = 120 frames of static image
   (~5–10 KB).  Prefer `self.wait(0.3–0.8)` unless intentional pause is needed.

3. **Prefer `play()` over `add()` for visual elements** — instant appearance is only
   appropriate for: background elements, axes/grid, title cards that should already
   "be there" when the scene starts. Everything else should animate in.

4. **Prefer `FadeOut()` over `remove()` for beat transitions** — `remove()` is an
   abrupt visual cut.  Exception: when using shrink-to-corner persistence pattern,
   `scale().to_corner()` is effectively a remove+reposition.

5. **Total scene duration ≈ sum of all play() run_time + sum of all wait() time**
   — This is what determines final video length.  If your target is 60 seconds, budget
   accordingly across beats.

6. **Higher quality = more frames per second** — high quality (1080p60fps) produces
   4× the frames of low quality (480p15fps) for the same content.  Use `-ql`/`-qk`
   during iteration, `-qh` for final.

### Frame budget example (60-second target, 5 beats)

```
Beat 1 (opening):     play(1.5s) + wait(0.5s) = 2.0s   → 120 frames @60fps
Beat 2 (main):       play(2.5s) + wait(0.5s) = 3.0s   → 180 frames
Beat 3 (development): play(3.0s) + wait(0.3s) = 3.3s   → 198 frames
Beat 4 (conclusion):  play(2.0s) + wait(0.8s) = 2.8s   → 168 frames
Beat 5 (ending):      play(1.0s) + wait(1.0s) = 2.0s   → 120 frames
── ─────────────────────────────────────────────────
Total:               13.1s animation + 3.1s wait = 16.2s
Remaining 43.8s: narration / TTS / muxing overhead (not in construct())
```
