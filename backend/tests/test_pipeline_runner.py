import json
from pathlib import Path

from backend.pipeline_runner import (
    _canonicalize_pipeline_artifacts,
    _cleanup_output_dir,
    _write_failure_diagnostics,
)


def test_canonicalize_preserves_raw_video_output_and_sets_final_video_output(tmp_path):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    final_output = task_dir / "final.mp4"

    render_dir = tmp_path / "render"
    render_dir.mkdir()
    rendered_video = render_dir / "rendered.mp4"
    rendered_video.write_bytes(b"video")

    scene_file = render_dir / "scene.py"
    scene_file.write_text("class GeneratedScene: pass", encoding="utf-8")

    logs: list[str] = []
    final_video, po_data = _canonicalize_pipeline_artifacts(
        task_dir=task_dir,
        output_path=final_output,
        final_video=str(rendered_video),
        pipeline_output={
            "video_output": str(rendered_video),
            "scene_file": str(scene_file),
        },
        log_callback=logs.append,
    )

    assert final_video == str(final_output)
    assert Path(final_video).exists()
    assert po_data is not None
    assert po_data["video_output"] == str(rendered_video)
    assert po_data["final_video_output"] == str(final_output)
    assert po_data["scene_file"] == str((task_dir / "scene.py").resolve())
    assert any("Imported rendered video" in line for line in logs)


def test_write_failure_diagnostics_persists_phase1_artifacts(tmp_path):
    task_dir = tmp_path / "task"

    class _FakeDispatcher:
        def get_phase1_failure_diagnostics(self):
            return {
                "raw_structured_output_present": True,
                "raw_structured_output_type": "dict",
                "scene_plan_validation_error": "build_spec missing beats",
            }

        def get_persistable_pipeline_output(self):
            return {"plan_text": "## Mode\nproof"}

    diagnostics_path = _write_failure_diagnostics(
        task_dir=task_dir,
        dispatcher=_FakeDispatcher(),
        error_message="phase1 failed",
    )

    assert diagnostics_path is not None
    assert diagnostics_path.exists()

    payload = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    assert payload["error_message"] == "phase1 failed"
    assert payload["phase1"]["scene_plan_validation_error"] == "build_spec missing beats"
    assert payload["pipeline_output_snapshot"]["plan_text"] == "## Mode\nproof"


def test_write_failure_diagnostics_prefers_frozen_phase1_snapshot(tmp_path):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "phase1_planning.json").write_text(
        json.dumps({"build_spec": {"mode": "proof"}}),
        encoding="utf-8",
    )

    class _FakeDispatcher:
        phase1_diagnostics_snapshot = {
            "accepted": True,
            "raw_structured_output_present": True,
            "raw_structured_output_type": "dict",
            "output_path": "old/path/phase1_planning.json",
        }

        def get_phase1_failure_diagnostics(self):
            return {
                "accepted": False,
                "raw_structured_output_present": False,
                "raw_structured_output_type": None,
            }

        def get_persistable_pipeline_output(self):
            return {"plan_text": "## Mode\nproof"}

    diagnostics_path = _write_failure_diagnostics(
        task_dir=task_dir,
        dispatcher=_FakeDispatcher(),
        error_message="phase2 failed",
    )

    payload = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    assert payload["phase1"]["accepted"] is True
    assert payload["phase1"]["raw_structured_output_present"] is True
    assert payload["phase1"]["output_path"] == str((task_dir / "phase1_planning.json").resolve())


def test_cleanup_output_dir_keeps_phase2_top_level_artifacts(tmp_path):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "phase2_scene.py").write_text("from manim import *\n", encoding="utf-8")
    (task_dir / "phase2_video.mp4").write_bytes(b"video")
    (task_dir / "phase2_implementation.json").write_text("{}", encoding="utf-8")
    (task_dir / "scratch.tmp").write_text("temp", encoding="utf-8")
    debug_dir = task_dir / "debug"
    debug_dir.mkdir()
    (debug_dir / "prompt_index.json").write_text("{}", encoding="utf-8")
    (debug_dir / "phase1.prompt.json").write_text("{}", encoding="utf-8")
    media_dir = task_dir / "media"
    media_dir.mkdir()
    (media_dir / "cache.mp4").write_bytes(b"cache")

    _cleanup_output_dir(task_dir, keep_mp4=True)

    assert (task_dir / "phase2_scene.py").exists()
    assert (task_dir / "phase2_video.mp4").exists()
    assert (task_dir / "phase2_implementation.json").exists()
    assert (debug_dir / "prompt_index.json").exists()
    assert (debug_dir / "phase1.prompt.json").exists()
    assert not (task_dir / "scratch.tmp").exists()
    assert not media_dir.exists()
