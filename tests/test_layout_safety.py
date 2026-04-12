import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from manim import RIGHT, Square


def _load_layout_safety_module():
    script_path = (
        Path(__file__).resolve().parents[1]
        / "plugins"
        / "manim-production"
        / "skills"
        / "layout-safety"
        / "scripts"
        / "layout_safety.py"
    )
    spec = spec_from_file_location("test_layout_safety_script", script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load layout safety script from {script_path}")
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_MODULE = _load_layout_safety_module()
CheckpointAudit = _MODULE.CheckpointAudit
LayoutReport = _MODULE.LayoutReport
assert_layout_safe = _MODULE.assert_layout_safe
audit_layout = _MODULE.audit_layout
get_mobject_bounds = _MODULE.get_mobject_bounds
summarize_layout_report = _MODULE.summarize_layout_report


class TestLayoutSafety:
    def test_detects_pairwise_overlap(self):
        left = Square(side_length=2.0)
        right = Square(side_length=2.0).shift(RIGHT * 0.5)

        report = audit_layout(("left", left), ("right", right))

        assert not report.ok
        assert any(issue.kind == "overlap" for issue in report.issues)
        assert "left overlaps right" in report.issues[0].message

    def test_detects_horizontal_crowding_when_gap_is_too_small(self):
        left = Square(side_length=1.0)
        right = Square(side_length=1.0).next_to(left, RIGHT, buff=0.05)

        report = audit_layout(("left", left), ("right", right), min_gap=0.2)

        assert not report.ok
        assert any(issue.kind == "crowding-horizontal" for issue in report.issues)

    def test_detects_frame_overflow(self):
        offscreen = Square(side_length=2.0).shift(RIGHT * 6)

        report = audit_layout(("offscreen", offscreen), frame_margin=0.25)

        assert not report.ok
        assert any(issue.kind == "frame-overflow" for issue in report.issues)

    def test_assert_layout_safe_raises_with_label(self):
        left = Square(side_length=2.0)
        right = Square(side_length=2.0).shift(RIGHT * 0.5)

        try:
            assert_layout_safe(
                ("left", left),
                ("right", right),
                label="beat-2",
            )
        except ValueError as exc:
            message = str(exc)
        else:
            raise AssertionError("expected ValueError")

        assert "beat-2" in message
        assert "layout safety check failed" in message

    def test_ok_report_summary_is_human_readable(self):
        left = Square(side_length=1.0)
        right = Square(side_length=1.0).next_to(left, RIGHT, buff=0.4)

        report = audit_layout(("left", left), ("right", right), min_gap=0.2)

        assert report.ok
        assert "no issues found" in summarize_layout_report(report)

    def test_bounds_match_expected_square_size(self):
        square = Square(side_length=2.0)

        bounds = get_mobject_bounds(square)

        assert round(bounds.width, 3) == 2.0
        assert round(bounds.height, 3) == 2.0

    def test_cli_main_reports_success(self, monkeypatch, capsys):
        monkeypatch.setattr(
            _MODULE,
            "run_layout_audit",
            lambda *args, **kwargs: [
                CheckpointAudit(label="final", report=LayoutReport(checked_count=2, issues=()))
            ],
        )

        exit_code = _MODULE.main(["scene.py", "GeneratedScene", "--checkpoint-mode", "final"])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "[final] layout safe" in captured.out

    def test_cli_main_reports_failure(self, monkeypatch, capsys):
        issue_report = audit_layout(
            ("left", Square(side_length=2.0)),
            ("right", Square(side_length=2.0).shift(RIGHT * 0.5)),
        )
        monkeypatch.setattr(
            _MODULE,
            "run_layout_audit",
            lambda *args, **kwargs: [
                CheckpointAudit(label="after-play-1", report=issue_report)
            ],
        )

        exit_code = _MODULE.main(["scene.py", "GeneratedScene"])
        captured = capsys.readouterr()

        assert exit_code == 1
        assert "layout issues" in captured.out

    def test_cli_main_reports_runtime_errors(self, monkeypatch, capsys):
        def _raise(*args, **kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(_MODULE, "run_layout_audit", _raise)

        exit_code = _MODULE.main(["scene.py", "GeneratedScene"])
        captured = capsys.readouterr()

        assert exit_code == 2
        assert "layout audit failed: boom" in captured.err
