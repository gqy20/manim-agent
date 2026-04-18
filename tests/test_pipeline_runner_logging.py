from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from backend.pipeline_runner import PipelineExecutionError, _pipeline_body


class TestPipelineRunnerLogging:
    @pytest.mark.asyncio
    async def test_pipeline_body_logs_success(self, caplog, tmp_path):
        req = SimpleNamespace(
            user_text="讲解圆周率",
            voice_id="female-tianmei",
            model="speech-2.8-hd",
            quality="high",
            no_tts=True,
            bgm_enabled=False,
            bgm_prompt=None,
            bgm_volume=0.12,
            target_duration_seconds=60,
            preset="default",
        )

        with (
            patch("manim_agent.pipeline.run_pipeline", new=AsyncMock(return_value="out/final.mp4")),
            caplog.at_level(logging.INFO),
        ):
            result = await _pipeline_body(
                req=req,
                task_id="task-1",
                output_path=str(tmp_path / "final.mp4"),
                voice_id=req.voice_id,
                model=req.model,
                quality=req.quality,
                no_tts=req.no_tts,
                bgm_enabled=req.bgm_enabled,
                bgm_prompt=req.bgm_prompt,
                bgm_volume=req.bgm_volume,
                target_duration_seconds=req.target_duration_seconds,
                cwd=str(tmp_path),
                max_turns=10,
                preset=req.preset,
                log_callback=lambda _line: None,
                event_callback=lambda _event: None,
                r2_client=None,
            )

        assert result == (str(Path("out/final.mp4").resolve()), None)
        events = [record.msg for record in caplog.records]
        assert "pipeline_started" in events
        assert "pipeline_completed" in events

    @pytest.mark.asyncio
    async def test_pipeline_body_logs_failure(self, caplog, tmp_path):
        req = SimpleNamespace(
            user_text="讲解圆周率",
            voice_id="female-tianmei",
            model="speech-2.8-hd",
            quality="high",
            no_tts=True,
            bgm_enabled=False,
            bgm_prompt=None,
            bgm_volume=0.12,
            target_duration_seconds=60,
            preset="default",
        )

        with (
            patch("manim_agent.pipeline.run_pipeline", new=AsyncMock(side_effect=RuntimeError("boom"))),
            caplog.at_level(logging.INFO),
            pytest.raises(PipelineExecutionError, match="RuntimeError: boom"),
        ):
            await _pipeline_body(
                req=req,
                task_id="task-1",
                output_path=str(tmp_path / "final.mp4"),
                voice_id=req.voice_id,
                model=req.model,
                quality=req.quality,
                no_tts=req.no_tts,
                bgm_enabled=req.bgm_enabled,
                bgm_prompt=req.bgm_prompt,
                bgm_volume=req.bgm_volume,
                target_duration_seconds=req.target_duration_seconds,
                cwd=str(tmp_path),
                max_turns=10,
                preset=req.preset,
                log_callback=lambda _line: None,
                event_callback=lambda _event: None,
                r2_client=None,
            )

        failure = next(record for record in caplog.records if record.msg == "pipeline_failed")
        assert failure.task_id == "task-1"
        assert failure.error_type == "RuntimeError"
