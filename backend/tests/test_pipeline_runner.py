from pathlib import Path
import json

from backend.pipeline_runner import _canonicalize_pipeline_artifacts, _write_failure_diagnostics


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
