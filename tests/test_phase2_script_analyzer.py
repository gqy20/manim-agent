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
    assert any("Unstable math glyph" in issue for issue in analysis.issues)
    assert any("Estimated script duration" in issue for issue in analysis.issues)
    assert any("hard-coded offset" in issue for issue in analysis.issues)


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
