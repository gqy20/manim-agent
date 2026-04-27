from __future__ import annotations

import json

from manim_agent.prompt_debug import write_prompt_artifact


def test_write_prompt_artifact_defaults_to_enabled(monkeypatch, tmp_path):
    monkeypatch.delenv("ENABLE_PROMPT_DEBUG", raising=False)

    result = write_prompt_artifact(
        output_dir=str(tmp_path),
        phase_id="phase1",
        phase_name="Planning",
        system_prompt="system",
        user_prompt="user",
    )

    assert result is not None
    assert (tmp_path / "debug" / "phase1.prompt.json").exists()


def test_write_prompt_artifact_can_be_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("ENABLE_PROMPT_DEBUG", "0")

    result = write_prompt_artifact(
        output_dir=str(tmp_path),
        phase_id="phase1",
        phase_name="Planning",
        system_prompt="system",
        user_prompt="user",
    )

    assert result is None
    assert not (tmp_path / "debug").exists()


def test_write_prompt_artifact_updates_index(monkeypatch, tmp_path):
    monkeypatch.setenv("ENABLE_PROMPT_DEBUG", "1")

    artifact_path = write_prompt_artifact(
        output_dir=str(tmp_path),
        phase_id="phase/1",
        phase_name="Planning",
        system_prompt="system prompt",
        user_prompt="user prompt",
        inputs={"topic": "fourier"},
        options_summary={"output_schema": "phase1_planning"},
        referenced_artifacts={"plan": "plan.md"},
    )

    assert artifact_path is not None
    artifact = json.loads((tmp_path / "debug" / "phase_1.prompt.json").read_text())
    index = json.loads((tmp_path / "debug" / "prompt_index.json").read_text())

    assert artifact["task_id"] == tmp_path.name
    assert artifact["phase_id"] == "phase/1"
    assert artifact["inputs"] == {"topic": "fourier"}
    assert artifact["options"]["output_schema"] == "phase1_planning"
    assert artifact["referenced_artifacts"] == {"plan": "plan.md"}
    assert index["task_id"] == tmp_path.name
    assert index["phases"][0]["phase_id"] == "phase/1"
