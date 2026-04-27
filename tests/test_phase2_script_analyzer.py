"""Tests for Phase 2 generated script static analysis."""

from __future__ import annotations

import json
from pathlib import Path

from manim_agent.phase2_script_analyzer import analyze_phase2_script


def _build_spec() -> dict:
    return {
        "beats": [
            {"id": "beat_001_setup"},
            {"id": "beat_002_rearrange"},
        ]
    }


def test_analyzer_accepts_beat_first_script(tmp_path: Path):
    script = tmp_path / "scene.py"
    script.write_text(
        """
from manim import *

class GeneratedScene(Scene):
    def construct(self):
        self.beat_001_setup()
        self.beat_002_rearrange()

    def beat_001_setup(self):
        self.play(FadeIn(Square()), run_time=5)
        self.wait(1)

    def beat_002_rearrange(self):
        self.play(FadeIn(Circle()), run_time=5)
        self.wait(1)
""",
        encoding="utf-8",
    )

    analysis = analyze_phase2_script(
        scene_file=str(script),
        scene_class="GeneratedScene",
        build_spec=_build_spec(),
        target_duration_seconds=10,
        output_dir=str(tmp_path),
    )

    assert analysis.accepted
    assert analysis.construct_calls[:2] == ["beat_001_setup", "beat_002_rearrange"]
    assert analysis.estimated_duration_seconds == 12
    assert analysis.beat_duration_seconds == {
        "beat_001_setup": 6,
        "beat_002_rearrange": 6,
    }


def test_analyzer_estimates_helpers_variables_and_fixed_loops(tmp_path: Path):
    script = tmp_path / "scene.py"
    script.write_text(
        """
from manim import *

class GeneratedScene(Scene):
    def construct(self):
        self.beat_001_setup()
        self.beat_002_rearrange()

    def _flash(self, name, run_time=0.5):
        self.play(FadeIn(Square()), run_time=run_time)

    def beat_001_setup(self):
        names = ["A", "B", "C"]
        flash_time = 0.7
        for index, name in enumerate(names):
            self._flash(name, run_time=flash_time)
            self.wait(0.1)
        self.wait(0.5)

    def beat_002_rearrange(self):
        step_time = 0.4
        for index in range(3):
            self._flash(index, run_time=step_time)
        self._flash("default")
        self.wait(0.5)
""",
        encoding="utf-8",
    )

    analysis = analyze_phase2_script(
        scene_file=str(script),
        scene_class="GeneratedScene",
        build_spec=_build_spec(),
        target_duration_seconds=4,
        output_dir=str(tmp_path),
    )

    assert analysis.accepted
    assert analysis.beat_duration_seconds == {
        "beat_001_setup": 2.9,
        "beat_002_rearrange": 2.2,
    }
    assert analysis.estimated_duration_seconds == 5.1


def test_analyzer_estimates_tuple_loops_with_none_bool_and_conditionals(tmp_path: Path):
    script = tmp_path / "scene.py"
    script.write_text(
        """
from manim import *

class GeneratedScene(Scene):
    def construct(self):
        self.beat_001_setup()

    def _flash(self, name, run_time=0.5):
        self.play(FadeIn(Square()), run_time=run_time)

    def beat_001_setup(self):
        moves = [
            (None, 1, False, True),
            (1, 2, False, True),
            (2, 1, True, False),
        ]
        for from_n, to_n, backtrack, should_visit in moves:
            if from_n is not None:
                rt = 0.50 if not backtrack else 0.42
                self.play(FadeIn(Circle()), run_time=rt)
                self.wait(0.12)
            if should_visit:
                self._flash(to_n, run_time=0.45)
                self.wait(0.18)
        self.wait(0.4)
""",
        encoding="utf-8",
    )

    analysis = analyze_phase2_script(
        scene_file=str(script),
        scene_class="GeneratedScene",
        build_spec={"beats": [{"id": "beat_001_setup"}]},
        target_duration_seconds=1,
        output_dir=str(tmp_path),
    )

    assert analysis.accepted
    assert analysis.beat_duration_seconds == {"beat_001_setup": 2.82}
    assert analysis.estimated_duration_seconds == 2.82


def test_analyzer_rejects_missing_beat_methods(tmp_path: Path):
    script = tmp_path / "scene.py"
    script.write_text(
        """
from manim import *

class GeneratedScene(Scene):
    def construct(self):
        self.play(FadeIn(Square()), run_time=3)
""",
        encoding="utf-8",
    )

    analysis = analyze_phase2_script(
        scene_file=str(script),
        scene_class="GeneratedScene",
        build_spec=_build_spec(),
        target_duration_seconds=10,
        output_dir=str(tmp_path),
    )

    assert not analysis.accepted
    assert any("Missing beat-first methods" in issue for issue in analysis.issues)


def test_analyzer_reports_syntax_error_location_and_source_line(tmp_path: Path):
    script = tmp_path / "scene.py"
    script.write_text(
        """
from manim import *

class GeneratedScene(Scene):
    def construct(self):
        self.beat_001_setup()
        self.beat_002_rearrange()

    def beat_001_setup(self):
        a = Square()
        b = Circle()
        self.play(Create(a), run_time=0.4, Create(b))
        self.wait(1)

    def beat_002_rearrange(self):
        self.wait(5)
""",
        encoding="utf-8",
    )

    analysis = analyze_phase2_script(
        scene_file=str(script),
        scene_class="GeneratedScene",
        build_spec=_build_spec(),
        target_duration_seconds=10,
        output_dir=str(tmp_path),
    )

    assert not analysis.accepted
    assert any("line 12" in issue for issue in analysis.issues)
    assert analysis.syntax_error is not None
    assert analysis.syntax_error["line"] == 12
    assert "Create(b)" in analysis.syntax_error["text"]


def test_analyzer_rejects_unstable_text_glyph_and_short_duration(tmp_path: Path):
    script = tmp_path / "scene.py"
    script.write_text(
        """
from manim import *

class GeneratedScene(Scene):
    def construct(self):
        self.beat_001_setup()
        self.beat_002_rearrange()

    def beat_001_setup(self):
        self.play(FadeIn(Text("a²")), run_time=1)
        self.wait(0.3)

    def beat_002_rearrange(self):
        offset = half_c * 0.72
        self.play(FadeIn(Square()), run_time=1)
        self.wait(0.3)
""",
        encoding="utf-8",
    )

    analysis = analyze_phase2_script(
        scene_file=str(script),
        scene_class="GeneratedScene",
        build_spec=_build_spec(),
        target_duration_seconds=20,
        output_dir=str(tmp_path),
    )

    assert not analysis.accepted
    assert any("Unstable math glyph" in w for w in analysis.warnings)
    assert any("Estimated script duration" in issue for issue in analysis.issues)
    assert any("hard-coded offset" in issue for issue in analysis.issues)
    assert analysis.beat_duration_seconds == {
        "beat_001_setup": 1.3,
        "beat_002_rearrange": 1.3,
    }


def test_analysis_model_dump_is_json_serializable(tmp_path: Path):
    script = tmp_path / "scene.py"
    script.write_text("class GeneratedScene: pass", encoding="utf-8")

    analysis = analyze_phase2_script(
        scene_file=str(script),
        scene_class="GeneratedScene",
        build_spec=_build_spec(),
        target_duration_seconds=10,
        output_dir=str(tmp_path),
    )

    json.dumps(analysis.model_dump())


def test_analyzer_accepts_existing_relative_path_without_double_join(tmp_path: Path):
    script = tmp_path / "scene.py"
    script.write_text(
        """
from manim import *

class GeneratedScene(Scene):
    def construct(self):
        self.beat_001_setup()
        self.beat_002_rearrange()

    def beat_001_setup(self):
        self.wait(5)

    def beat_002_rearrange(self):
        self.wait(5)
""",
        encoding="utf-8",
    )

    relative_script = Path("scene.py")
    old_cwd = Path.cwd()
    try:
        import os

        os.chdir(tmp_path)
        analysis = analyze_phase2_script(
            scene_file=str(relative_script),
            scene_class="GeneratedScene",
            build_spec=_build_spec(),
            target_duration_seconds=10,
            output_dir=str(tmp_path),
        )
    finally:
        os.chdir(old_cwd)

    assert analysis.accepted
    assert Path(analysis.scene_file) == relative_script
