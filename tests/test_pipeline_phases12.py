"""Tests for pipeline_phases12 module (Phase1 planning + Phase2 implementation)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestBuildScenePlanPrompt:
    """Tests for _build_scene_plan_prompt."""

    def test_returns_string(self):
        from manim_agent.pipeline_phases12 import build_scene_plan_prompt

        result = build_scene_plan_prompt(
            user_text="解释傅里叶变换",
            target_duration_seconds=60,
            cwd=".",
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_includes_target_duration(self):
        from manim_agent.pipeline_phases12 import build_scene_plan_prompt
        from manim_agent.prompt_builder import format_target_duration

        result = build_scene_plan_prompt(
            user_text="解释傅里叶变换",
            target_duration_seconds=60,
            cwd=".",
        )
        assert format_target_duration(60) in result

    def test_includes_scene_plan_skill_reference(self):
        from manim_agent.pipeline_phases12 import build_scene_plan_prompt

        result = build_scene_plan_prompt(
            user_text="解释傅里叶变换",
            target_duration_seconds=60,
            cwd=".",
        )
        assert "scene-plan" in result.lower() or "plugin" in result.lower()

    def test_empty_user_text_still_returns_prompt(self):
        from manim_agent.pipeline_phases12 import build_scene_plan_prompt

        result = build_scene_plan_prompt(
            user_text="",
            target_duration_seconds=30,
            cwd=".",
        )
        assert isinstance(result, str)

    def test_requires_structured_build_spec_output(self):
        from manim_agent.pipeline_phases12 import build_scene_plan_prompt

        result = build_scene_plan_prompt(
            user_text="测试",
            target_duration_seconds=60,
            cwd=".",
        )
        assert "build_spec" in result
        assert "structured_output" in result

    def test_can_derive_minimal_build_spec_from_visible_plan(self):
        from manim_agent.pipeline_phases12 import derive_scene_plan_output_from_visible_plan

        plan_text = (
            "## Mode\nproof-walkthrough\n"
            "## Learning Goal\nUnderstand the rearrangement proof.\n"
            "## Audience\nHigh-school students.\n"
            "## Beat List\n"
            "1. Introduce the right triangle.\n"
            "2. Rearrange the copies inside the square.\n"
            "## Narration Outline\n"
            "1. Set up the triangle and side labels.\n"
            "2. Explain why area is preserved.\n"
            "## Visual Risks\nAvoid clutter.\n"
            "## Build Handoff\nImplement with clear labels.\n"
        )

        result = derive_scene_plan_output_from_visible_plan(
            plan_text,
            target_duration_seconds=60,
        )

        assert result is not None
        assert result.build_spec.mode == "proof-walkthrough"
        assert len(result.build_spec.beats) == 2
        assert result.build_spec.beats[0].id == "beat_001_introduce_the_right_triangle"
        assert result.build_spec.beats[1].narration_intent == "Explain why area is preserved."


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
    async def test_phase1_rejects_empty_collected_text(self):
        from manim_agent.pipeline_phases12 import run_phase1_planning

        dispatcher = MagicMock()
        dispatcher.collected_text = []
        dispatcher.get_scene_plan_output.return_value = None
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
            with pytest.raises(RuntimeError, match="scene-plan"):
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
    async def test_phase1_stops_iteration_on_scene_plan(self):
        """Verify that a scene plan in collected_text satisfies the validation."""
        from manim_agent.pipeline_phases12 import run_phase1_planning
        from manim_agent.pipeline_gates import has_visible_scene_plan

        plan_text = (
            "# Scene Plan\n## Mode\neducational\n## Learning Goal\ntest\n"
            "## Audience\nuniversity students\n"
            "## Beat List\n1. Intro\n## Narration Outline\ntest\n"
            "## Visual Risks\nnone\n## Build Handoff\nok"
        )

        assert has_visible_scene_plan([plan_text]) is True

    @pytest.mark.asyncio
    async def test_phase1_requires_structured_build_spec_when_visible_plan_cannot_be_derived(self):
        from manim_agent.pipeline_phases12 import run_phase1_planning

        plan_text = (
            "# Scene Plan\n## Mode\neducational\n## Learning Goal\ntest\n"
            "## Audience\nuniversity students\n"
            "## Beat List\n\n## Narration Outline\ntest\n"
            "## Visual Risks\nnone\n## Build Handoff\nok"
        )
        dispatcher = MagicMock()
        dispatcher.collected_text = [plan_text]
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
        assert "Structured planning output missing or invalid." in printed
        assert "raw_structured_output_present=False" in printed
        assert "scene_plan_validation_error=missing build_spec" in printed

    @pytest.mark.asyncio
    async def test_phase1_accepts_valid_structured_build_spec(self):
        from manim_agent.schemas import Phase1PlanningOutput as ScenePlanOutput
        from manim_agent.pipeline_phases12 import run_phase1_planning

        plan_text = (
            "# Scene Plan\n## Mode\neducational\n## Learning Goal\ntest\n"
            "## Audience\nuniversity students\n"
            "## Beat List\n1. Intro\n## Narration Outline\ntest\n"
            "## Visual Risks\nnone\n## Build Handoff\nok"
        )
        dispatcher = MagicMock()
        dispatcher.collected_text = [plan_text]
        dispatcher.get_scene_plan_output.return_value = ScenePlanOutput.model_validate(
            {
                "markdown_plan": plan_text,
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

        planning_options = MagicMock()
        planning_options.allowed_tools = []
        planning_options.max_turns = 16

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
                resolved_cwd=".",
                dispatcher=dispatcher,
                event_callback=None,
            )

        assert result == {"turns": 1}
        assert dispatcher.partial_plan_text == plan_text
        assert dispatcher.partial_build_spec["beats"][0]["id"] == "beat_001_intro"

    @pytest.mark.asyncio
    async def test_phase1_repairs_structured_build_spec_from_visible_plan(self):
        from manim_agent.schemas import Phase1PlanningOutput as ScenePlanOutput
        from manim_agent.pipeline_phases12 import run_phase1_planning

        plan_text = (
            "## Mode\neducational\n## Learning Goal\ntest\n"
            "## Audience\nuniversity students\n"
            "## Beat List\n1. Intro\n2. Proof\n"
            "## Narration Outline\n1. Introduce the setup\n2. Explain the proof\n"
            "## Visual Risks\nnone\n## Build Handoff\nok"
        )
        dispatcher = MagicMock()
        dispatcher.collected_text = [plan_text]
        repaired_output = ScenePlanOutput.model_validate({
            "markdown_plan": plan_text,
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
        scene_plan_outputs = [None, repaired_output]

        def _get_scene_plan_output():
            value = scene_plan_outputs.pop(0)
            return value

        dispatcher.get_scene_plan_output.side_effect = _get_scene_plan_output
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
            result = await run_phase1_planning(
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

        assert result == {"turns": 1}
        assert dispatcher.partial_build_spec["beats"][0]["id"] == "beat_001_intro"
        assert dispatcher.partial_build_spec["beats"][1]["narration_intent"] == "Explain the proof"
        printed = "\n".join(call.args[0] for call in dispatcher._print.call_args_list if call.args)
        assert "Running a no-tools repair pass" in printed
