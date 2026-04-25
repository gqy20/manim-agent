"""Tests for pipeline_phases12 module (Phase1 planning + Phase2 implementation)."""

from unittest.mock import MagicMock, patch

import pytest


class TestBuildScenePlanPrompt:
    """Tests for _build_scene_plan_prompt."""

    def test_returns_string(self):
        from manim_agent.pipeline_phases12 import build_scene_plan_prompt

        result = build_scene_plan_prompt(
            user_text="解释傅里叶变换",
            target_duration_seconds=60,
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_includes_target_duration(self):
        from manim_agent.pipeline_phases12 import build_scene_plan_prompt
        from manim_agent.prompt_builder import format_target_duration

        result = build_scene_plan_prompt(
            user_text="解释傅里叶变换",
            target_duration_seconds=60,
        )
        assert format_target_duration(60) in result

    def test_does_not_require_plugin_or_scene_plan_visible_format(self):
        from manim_agent.pipeline_phases12 import build_scene_plan_prompt

        result = build_scene_plan_prompt(
            user_text="解释傅里叶变换",
            target_duration_seconds=60,
        )
        assert "scene-plan" not in result.lower()
        assert "plugin rooted at" not in result
        assert "structured_output" in result

    def test_does_not_expose_task_or_plugin_paths(self):
        from manim_agent.pipeline_phases12 import build_scene_plan_prompt

        result = build_scene_plan_prompt(
            user_text="解释傅里叶变换",
            target_duration_seconds=60,
        )

        assert "D:/repo/backend/output/task123" not in result
        assert "plugin rooted at" not in result
        assert "Do not use Bash, Read, Glob, Grep" in result

    def test_empty_user_text_still_returns_prompt(self):
        from manim_agent.pipeline_phases12 import build_scene_plan_prompt

        result = build_scene_plan_prompt(
            user_text="",
            target_duration_seconds=30,
        )
        assert isinstance(result, str)

    def test_requires_structured_build_spec_output(self):
        from manim_agent.pipeline_phases12 import build_scene_plan_prompt

        result = build_scene_plan_prompt(
            user_text="测试",
            target_duration_seconds=60,
        )
        assert "build_spec" in result
        assert "structured_output" in result
        assert "Markdown plan" not in result

    def test_segments_mode_includes_segment_planning_guidance(self):
        from manim_agent.pipeline_phases12 import build_scene_plan_prompt

        result = build_scene_plan_prompt(
            user_text="测试",
            target_duration_seconds=60,
            render_mode="segments",
        )

        assert "Downstream render mode: segments" in result
        assert "segment-required beat" in result


class TestBuildImplementationPrompt:
    """Tests for _build_implementation_prompt."""

    def test_returns_string(self):
        from manim_agent.pipeline_phases12 import build_implementation_prompt

        plan_text = """
## Mode
educational

## Learning Goal
理解傅里叶变换原理

## Beat List
1. 周期函数介绍
2. 频域概念
"""
        result = build_implementation_prompt(
            user_text="解释傅里叶变换",
            target_duration_seconds=60,
            plan_text=plan_text,
            cwd=".",
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_includes_plan_text(self):
        from manim_agent.pipeline_phases12 import build_implementation_prompt

        plan_text = "## Beat List\n1. First beat"
        result = build_implementation_prompt(
            user_text="测试",
            target_duration_seconds=60,
            plan_text=plan_text,
            cwd=".",
        )
        assert plan_text in result

    def test_mentions_scene_build_skill(self):
        from manim_agent.pipeline_phases12 import build_implementation_prompt

        result = build_implementation_prompt(
            user_text="测试",
            target_duration_seconds=60,
            plan_text="## Beat List\n1. Test",
            cwd=".",
        )
        assert "scene-build" in result.lower() or "implementation" in result.lower()

    def test_segments_mode_requires_real_segment_delivery_and_no_placeholder_success(self):
        from manim_agent.pipeline_phases12 import build_implementation_prompt

        result = build_implementation_prompt(
            user_text="测试",
            target_duration_seconds=60,
            plan_text="## Beat List\n1. Opening\n2. Main",
            cwd=".",
            render_mode="segments",
        )

        assert "If you cannot produce the real beat-level MP4 files" in result
        assert "Do not mark `segment_render_complete` true as a placeholder" in result
        assert "Do not leave `implemented_beats` empty" in result
        assert "pipeline can discover those files automatically" in result

    def test_includes_structured_build_spec_when_provided(self):
        from manim_agent.pipeline_phases12 import build_implementation_prompt

        result = build_implementation_prompt(
            user_text="测试",
            target_duration_seconds=60,
            plan_text="## Beat List\n1. Intro",
            build_spec={
                "mode": "proof-walkthrough",
                "learning_goal": "Explain the proof.",
                "audience": "students",
                "target_duration_seconds": 60,
                "beats": [
                    {
                        "id": "beat_001_intro",
                        "title": "Intro",
                        "visual_goal": "Show the setup",
                        "narration_intent": "Introduce the problem",
                        "target_duration_seconds": 10,
                        "required_elements": ["triangle"],
                        "segment_required": True,
                    }
                ],
            },
            cwd=".",
        )

        assert "Approved structured build specification (JSON)" in result
        assert '"id": "beat_001_intro"' in result


class TestBuildOutputRepairPrompt:
    def test_segment_mode_without_video_output_mentions_segment_paths(self):
        from manim_agent.prompt_builder import build_output_repair_prompt

        result = build_output_repair_prompt(
            user_text="test",
            target_duration_seconds=60,
            plan_text="## Beat List\n1. Opening",
            partial_output={"render_mode": "segments"},
            video_output=None,
            segment_video_paths=["segments/beat_001.mp4", "segments/beat_002.mp4"],
            render_mode="segments",
        )

        assert "segment_video_paths" in result
        assert "segments/beat_001.mp4" in result
        assert "Keep `video_output` as null" in result
        assert "Do not leave `implemented_beats` empty" in result


class TestPhase1ValidationLogic:
    """Tests for Phase 1 validation logic in run_phase1_planning.

    These tests mock query at a lower level to avoid SDK prompt-type validation.
    """

    @pytest.mark.asyncio
    async def test_phase1_rejects_missing_structured_output(self):
        from manim_agent.pipeline_phases12 import run_phase1_planning

        dispatcher = MagicMock()
        dispatcher.collected_text = []
        dispatcher.get_scene_plan_output.return_value = None
        dispatcher.get_phase1_failure_diagnostics.return_value = {
            "raw_structured_output_present": False,
            "raw_structured_output_type": None,
            "scene_plan_validation_error": None,
        }
        dispatcher.result_summary = {"turns": 0}
        dispatcher.implementation_started = False
        dispatcher.implementation_start_reason = None
        dispatcher._msg_count = 0
        dispatcher._msg_type_stats = {}
        dispatcher._assistant_msg_count = 0
        dispatcher.tool_use_count = 0
        dispatcher.tool_stats = {}
        event_callback = MagicMock()

        planning_options = MagicMock()
        planning_options.session_id = "test-session"
        planning_options.allowed_tools = []
        planning_options.max_turns = 16
        planning_options.plugins = []

        async def empty_iter():
            return
            yield

        with patch("manim_agent.pipeline_phases12.query") as mock_query:
            mock_query.return_value = empty_iter()
            with pytest.raises(RuntimeError, match="structured build_spec"):
                await run_phase1_planning(
                    planning_prompt="test prompt",
                    target_duration_seconds=60,
                    planning_options=planning_options,
                    system_prompt="system",
                    quality="high",
                    prompt_file=None,
                    log_callback=None,
                    resolved_cwd=".",
                    dispatcher=dispatcher,
                    event_callback=event_callback,
                )

    @pytest.mark.asyncio
    async def test_phase1_reports_validation_diagnostics_when_structured_output_invalid(self):
        from manim_agent.pipeline_phases12 import run_phase1_planning

        dispatcher = MagicMock()
        dispatcher.collected_text = []
        dispatcher.get_scene_plan_output.return_value = None
        dispatcher.get_phase1_failure_diagnostics.return_value = {
            "raw_structured_output_present": False,
            "raw_structured_output_type": None,
            "scene_plan_validation_error": "missing build_spec",
        }
        dispatcher.result_summary = {"turns": 1}
        dispatcher._print = MagicMock()

        planning_options = MagicMock()
        planning_options.allowed_tools = []
        planning_options.max_turns = 16

        async def empty_iter():
            return
            yield

        with patch("manim_agent.pipeline_phases12.query") as mock_query:
            mock_query.return_value = empty_iter()
            with pytest.raises(RuntimeError, match="structured build_spec"):
                await run_phase1_planning(
                    planning_prompt="test prompt",
                    target_duration_seconds=60,
                    planning_options=planning_options,
                    system_prompt="system",
                    quality="high",
                    prompt_file=None,
                    log_callback=None,
                    resolved_cwd=".",
                    dispatcher=dispatcher,
                    event_callback=None,
                )

        printed = "\n".join(call.args[0] for call in dispatcher._print.call_args_list if call.args)
        assert "Structured Phase 1 planning output missing or invalid." in printed
        assert "raw_structured_output_present=False" in printed
        assert "scene_plan_validation_error=missing build_spec" in printed

    @pytest.mark.asyncio
    async def test_phase1_accepts_valid_structured_build_spec(self, tmp_path):
        from manim_agent.pipeline_phases12 import run_phase1_planning
        from manim_agent.schemas import Phase1PlanningOutput as ScenePlanOutput

        dispatcher = MagicMock()
        dispatcher.collected_text = []
        dispatcher.get_scene_plan_output.return_value = ScenePlanOutput.model_validate(
            {
                "build_spec": {
                    "mode": "proof-walkthrough",
                    "learning_goal": "Test goal",
                    "audience": "university students",
                    "target_duration_seconds": 60,
                    "beats": [
                        {
                            "id": "beat_001_intro",
                            "title": "Intro",
                            "visual_goal": "Show setup",
                            "narration_intent": "Introduce setup",
                            "target_duration_seconds": 12,
                            "required_elements": ["triangle"],
                            "segment_required": True,
                        }
                    ],
                },
            }
        )
        dispatcher.result_summary = {"turns": 1}
        dispatcher._print = MagicMock()
        dispatcher.get_phase1_failure_diagnostics.return_value = {
            "raw_structured_output_present": True,
            "raw_structured_output_type": "dict",
            "scene_plan_validation_error": None,
        }
        planning_options = MagicMock()
        planning_options.allowed_tools = []
        planning_options.max_turns = 16
        event_callback = MagicMock()

        async def empty_iter():
            return
            yield

        with patch("manim_agent.pipeline_phases12.query") as mock_query:
            mock_query.return_value = empty_iter()
            result = await run_phase1_planning(
                planning_prompt="test prompt",
                target_duration_seconds=60,
                planning_options=planning_options,
                system_prompt="system",
                quality="high",
                prompt_file=None,
                log_callback=None,
                resolved_cwd=str(tmp_path),
                dispatcher=dispatcher,
                event_callback=event_callback,
            )

        assert result == {"turns": 1}
        assert "## Mode\nproof-walkthrough" in dispatcher.partial_plan_text
        assert "## Beat List" in dispatcher.partial_plan_text
        assert "1. Intro" in dispatcher.partial_plan_text
        assert dispatcher.partial_build_spec["beats"][0]["id"] == "beat_001_intro"
        phase1_path = tmp_path / "phase1_planning.json"
        assert phase1_path.exists()
        assert dispatcher.phase1_output_path == str(phase1_path.resolve())
        assert dispatcher.phase1_diagnostics_snapshot["accepted"] is True
        assert dispatcher.phase1_diagnostics_snapshot["build_spec_beat_count"] == 1
        status_event = event_callback.call_args.args[0]
        assert status_event.data.pipeline_output["phase1_planning"]["build_spec"]["mode"] == (
            "proof-walkthrough"
        )
        assert status_event.data.pipeline_output["target_duration_seconds"] == 60
        assert "## Beat List" in status_event.data.pipeline_output["plan_text"]
        dispatcher.get_persistable_pipeline_output.assert_not_called()

    @pytest.mark.asyncio
    async def test_phase1_normalizes_target_duration_and_renders_plan_text(self, tmp_path):
        from manim_agent.pipeline_phases12 import run_phase1_planning
        from manim_agent.schemas import Phase1PlanningOutput as ScenePlanOutput

        dispatcher = MagicMock()
        dispatcher.collected_text = []
        dispatcher.get_scene_plan_output.return_value = ScenePlanOutput.model_validate(
            {
                "build_spec": {
                    "mode": "educational",
                    "learning_goal": "Test goal",
                    "audience": "university students",
                    "target_duration_seconds": 45,
                    "beats": [
                        {
                            "id": "beat_001_intro",
                            "title": "Intro",
                            "visual_goal": "Show setup",
                            "narration_intent": "Introduce setup",
                            "target_duration_seconds": 12,
                            "required_elements": [],
                            "segment_required": True,
                        }
                    ],
                },
            }
        )
        dispatcher.result_summary = {"turns": 1}
        dispatcher._print = MagicMock()
        dispatcher.get_phase1_failure_diagnostics.return_value = {
            "raw_structured_output_present": True,
            "raw_structured_output_type": "dict",
            "scene_plan_validation_error": None,
        }

        planning_options = MagicMock()
        planning_options.allowed_tools = []
        planning_options.max_turns = 16

        async def empty_iter():
            return
            yield

        with patch("manim_agent.pipeline_phases12.query") as mock_query:
            mock_query.return_value = empty_iter()
            await run_phase1_planning(
                planning_prompt="test prompt",
                target_duration_seconds=60,
                planning_options=planning_options,
                system_prompt="system",
                quality="high",
                prompt_file=None,
                log_callback=None,
                resolved_cwd=str(tmp_path),
                dispatcher=dispatcher,
                event_callback=None,
            )

        assert "## Mode\neducational" in dispatcher.partial_plan_text
        assert "target_duration_seconds: 12" in dispatcher.partial_plan_text
        assert dispatcher.partial_build_spec["target_duration_seconds"] == 60
        printed = "\n".join(call.args[0] for call in dispatcher._print.call_args_list if call.args)
        assert "build_spec.target_duration_seconds did not match the request" in printed

    def test_render_build_spec_markdown_is_deterministic(self):
        from manim_agent.pipeline_phases12 import render_build_spec_markdown
        from manim_agent.schemas import Phase1PlanningOutput as ScenePlanOutput

        output = ScenePlanOutput.model_validate({
            "build_spec": {
                "mode": "educational",
                "learning_goal": "test",
                "audience": "university students",
                "target_duration_seconds": 60,
                "beats": [
                    {
                        "id": "beat_001_intro",
                        "title": "Intro",
                        "visual_goal": "Show setup",
                        "narration_intent": "Introduce the setup",
                        "target_duration_seconds": 20,
                        "required_elements": [],
                        "segment_required": True,
                    },
                    {
                        "id": "beat_002_proof",
                        "title": "Proof",
                        "visual_goal": "Explain the proof",
                        "narration_intent": "Explain the proof",
                        "target_duration_seconds": 40,
                        "required_elements": [],
                        "segment_required": True,
                    },
                ],
            },
        })

        result = render_build_spec_markdown(output, target_duration_seconds=60)

        assert "## Mode\neducational" in result
        assert "1. Intro" in result
        assert "2. Proof" in result
        assert "id: `beat_001_intro`" in result
        assert "segment_required: yes" in result
