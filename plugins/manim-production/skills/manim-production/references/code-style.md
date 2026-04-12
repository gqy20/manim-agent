# Code Style

- Prefer clear object names over anonymous chained expressions.
- Extract repeated coordinates or colors into named variables.
- Prefer Manim relationships like `next_to`, `align_to`, `to_edge`, and groups over excessive hard-coded screen coordinates.
- Use `VGroup` to manage related elements.
- Keep animation order readable. The code should show the teaching sequence.
- Add a brief comment only when the visual logic would otherwise be hard to parse.
