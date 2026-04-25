"""Tests for exposing pipeline dispatcher diagnostics on early failures."""

from unittest.mock import AsyncMock, patch

import pytest

from manim_agent import pipeline


@pytest.mark.asyncio
async def test_dispatcher_ref_is_available_when_phase1_fails(tmp_path):
    dispatcher_ref = []

    with patch(
        "manim_agent.pipeline.run_phase1_planning",
        new_callable=AsyncMock,
        side_effect=RuntimeError("phase1 boom"),
    ):
        with pytest.raises(RuntimeError, match="phase1 boom"):
            await pipeline.run_pipeline(
                user_text="test",
                output_path=str(tmp_path / "final.mp4"),
                no_tts=True,
                cwd=str(tmp_path),
                _dispatcher_ref=dispatcher_ref,
            )

    assert len(dispatcher_ref) == 1
    diagnostics = dispatcher_ref[0].get_phase1_failure_diagnostics()
    assert diagnostics["raw_structured_output_present"] is False
    assert diagnostics["raw_structured_output_type"] is None
