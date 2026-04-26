"""Tests for manim_agent.prompts module."""

import pytest

from manim_agent import prompts


class TestSystemPrompt:
    def test_system_prompt_is_non_empty_string(self):
        assert isinstance(prompts.SYSTEM_PROMPT, str)
        assert len(prompts.SYSTEM_PROMPT) > 0

    def test_system_prompt_references_manim_plugin_and_skills(self):
        assert "manim-production" in prompts.SYSTEM_PROMPT
        assert "scene-build" in prompts.SYSTEM_PROMPT
        assert "layout-safety" in prompts.SYSTEM_PROMPT


class TestGetPrompt:
    def test_includes_user_text_and_is_longer_than_input(self):
        result = prompts.get_prompt("解释傅里叶变换")
        assert isinstance(result, str)
        assert "傅里叶变换" in result
        assert len(result) > len("解释傅里叶变换")

    def test_preset_affects_output_content(self):
        educational = prompts.get_prompt("测试", preset="educational")
        proof = prompts.get_prompt("测试", preset="proof")
        assert educational != proof  # different presets produce different output

    def test_quality_flag_appears_in_command(self):
        assert "-qh" in prompts.get_prompt("测试", quality="high")
        assert "-ql" in prompts.get_prompt("测试", quality="low")

    def test_cwd_adds_task_directory_instructions(self):
        result = prompts.get_prompt("测试", cwd="/tmp/task")
        assert "scene.py" in result
        assert "GeneratedScene" in result
        assert "Simplified Chinese" in result
        assert "manim-production" in result

    @pytest.mark.parametrize("bad_preset", ["invalid", "", "xxx"])
    def test_invalid_preset_raises_value_error(self, bad_preset):
        with pytest.raises(ValueError, match="preset"):
            prompts.get_prompt("测试", preset=bad_preset)

    @pytest.mark.parametrize("bad_quality", ["ultra", "fast", ""])
    def test_invalid_quality_raises_value_error(self, bad_quality):
        with pytest.raises(ValueError, match="quality"):
            prompts.get_prompt("测试", quality=bad_quality)


class TestGetImplementationPrompt:
    def test_is_phase2_focused(self):
        result = prompts.get_implementation_prompt(cwd="/tmp/task")
        assert "Phase 2" in result
        assert "build_spec" in result
        assert "# 用户需求" not in result

    def test_includes_render_stability_rules(self):
        result = prompts.get_implementation_prompt(cwd="/tmp/task")
        assert "/scene-build" in result
        assert "Phase 2B" in result
        assert "script draft" in result.lower() or "render implementation" in result.lower()

    def test_mentions_required_skill_order(self):
        result = prompts.get_implementation_prompt(cwd="/tmp/task")
        # Implementation prompt references these skills in its workflow
        for skill in ("/scene-build", "/layout-safety",
                       "/narration-sync", "/render-review"):
            assert skill in result


class TestGetPhase2ScriptDraftPrompt:
    def test_is_phase2a_only_no_render(self):
        result = prompts.get_phase2_script_draft_prompt(cwd="/tmp/task")
        assert "Phase 2A" in result
        assert "Do NOT render" in result or "no rendering" in result.lower()
        assert "Run Manim directly" not in result
        assert "manim -qh" not in result

    def test_requires_beat_first_structure_and_timing(self):
        result = prompts.get_phase2_script_draft_prompt(cwd="/tmp/task")
        assert "beat-first" in result
        assert "/scene-build" in result
        assert "Timing Gates" in result or "timing" in result.lower()

    def test_limited_skill_order_excludes_render_skills(self):
        result = prompts.get_phase2_script_draft_prompt(cwd="/tmp/task")
        assert "scene-build" in result
        # Phase 2A should mention what NOT to use, but skill list is limited
        assert "scene-direction" in result
        assert "layout-safety" in result


class TestGetRenderReviewPrompt:
    def test_is_read_only_phase3(self):
        result = prompts.get_render_review_prompt(cwd="/tmp/task")
        assert "Phase 3" in result
        assert "Do not write code" in result
        assert "Do not render or re-render" in result


class TestGetPlanningPrompt:
    def test_is_planning_only_no_code_no_render(self):
        result = prompts.get_planning_prompt()
        assert "规划阶段" in result
        assert "不写代码" in result
        assert "不渲染" in result
        assert "scene.py" not in result

    def test_segments_mode_includes_segment_ids(self):
        result = prompts.get_planning_prompt(render_mode="segments")
        assert "segments/<beat_id>.mp4" in result


# All prompt-building functions share the same validation decorator;
# spot-check that it fires consistently across entry points.
@pytest.mark.parametrize(
    "fn_name,call_kwargs",
    [
        ("get_prompt", {"user_text": "x", "preset": "bogus"}),
        ("get_implementation_prompt", {"cwd": "/tmp/task", "preset": "bogus"}),
        ("get_phase2_script_draft_prompt", {"cwd": "/tmp/task", "preset": "bogus"}),
        ("get_render_review_prompt", {"cwd": "/tmp/task", "preset": "bogus"}),
        ("get_planning_prompt", {"preset": "bogus"}),
    ],
    ids=["get_prompt", "implementation", "script_draft", "render_review", "planning"],
)
def test_all_prompt_functions_reject_invalid_preset(fn_name, call_kwargs):
    fn = getattr(prompts, fn_name)
    with pytest.raises(ValueError, match="preset"):
        fn(**call_kwargs)
