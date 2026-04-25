"""Tests for manim_agent.prompts module."""

import pytest

from manim_agent import prompts


class TestSystemPrompt:
    def test_system_prompt_is_string(self):
        assert isinstance(prompts.SYSTEM_PROMPT, str)
        assert len(prompts.SYSTEM_PROMPT) > 0

    def test_system_prompt_contains_role(self):
        assert "Manim" in prompts.SYSTEM_PROMPT or "manim" in prompts.SYSTEM_PROMPT.lower()

    def test_system_prompt_contains_output_format(self):
        assert (
            "render" in prompts.SYSTEM_PROMPT.lower()
            or "output" in prompts.SYSTEM_PROMPT.lower()
        )

    def test_system_prompt_contains_workflow_rules(self):
        assert "manim" in prompts.SYSTEM_PROMPT.lower() or "render" in prompts.SYSTEM_PROMPT.lower()

    def test_system_prompt_mentions_manim_production_plugin(self):
        assert "manim-production" in prompts.SYSTEM_PROMPT
        assert "scene-build" in prompts.SYSTEM_PROMPT
        assert "layout-safety" in prompts.SYSTEM_PROMPT


class TestGetPrompt:
    def test_get_prompt_default(self):
        result = prompts.get_prompt("解释傅里叶变换")
        assert isinstance(result, str)
        assert "傅里叶变换" in result
        assert len(result) > len("解释傅里叶变换")

    def test_get_prompt_contains_system_prompt(self):
        result = prompts.get_prompt("测试文本")
        assert "render" in result.lower() or "output" in result.lower()

    def test_get_prompt_educational_preset(self):
        result = prompts.get_prompt("测试", preset="educational")
        assert "教学" in result or "循序渐进" in result or "教育" in result

    def test_get_prompt_presentation_preset(self):
        result = prompts.get_prompt("测试", preset="presentation")
        assert "演示" in result or "简洁" in result or "汇报" in result

    def test_get_prompt_proof_preset(self):
        result = prompts.get_prompt("测试", preset="proof")
        assert "证明" in result or "推导" in result or "逻辑" in result

    def test_get_prompt_concept_preset(self):
        result = prompts.get_prompt("测试", preset="concept")
        assert "可视化" in result or "直观" in result or "比喻" in result

    def test_get_prompt_invalid_preset_raises(self):
        with pytest.raises(ValueError, match="preset"):
            prompts.get_prompt("测试", preset="invalid_preset")

    def test_get_prompt_quality_high(self):
        result = prompts.get_prompt("测试", quality="high")
        assert "-qh" in result

    def test_get_prompt_quality_medium(self):
        result = prompts.get_prompt("测试", quality="medium")
        assert "-qm" in result

    def test_get_prompt_quality_low(self):
        result = prompts.get_prompt("测试", quality="low")
        assert "-ql" in result

    def test_get_prompt_quality_invalid_raises(self):
        with pytest.raises(ValueError, match="quality"):
            prompts.get_prompt("测试", quality="ultra")

    def test_get_prompt_task_directory_instructions_include_chinese_narration(self):
        result = prompts.get_prompt("测试", cwd="/tmp/task")
        assert "scene.py" in result
        assert "GeneratedScene" in result
        assert "Run Manim directly" in result
        assert "Simplified Chinese" in result

    def test_get_prompt_mentions_manim_production_plugin_when_task_directory_is_set(self):
        result = prompts.get_prompt("测试", cwd="/tmp/task")
        assert "manim-production" in result

    def test_get_prompt_mentions_scene_build_when_task_directory_is_set(self):
        result = prompts.get_prompt("测试", cwd="/tmp/task")
        assert "scene-build" in result
        assert "layout-safety" in result


class TestGetImplementationPrompt:
    def test_get_implementation_prompt_is_phase2_only(self):
        result = prompts.get_implementation_prompt(cwd="/tmp/task")

        assert "Phase 2" in result
        assert "build_spec" in result
        assert "TTS" in result
        assert "muxing" in result
        assert "# 用户需求" not in result

    def test_get_implementation_prompt_mentions_skill_order(self):
        result = prompts.get_implementation_prompt(cwd="/tmp/task")

        assert "scene-build" in result
        assert "scene-direction" in result
        assert "layout-safety" in result
        assert "narration-sync" in result
        assert "render-review" in result

    def test_get_implementation_prompt_contains_render_stable_generation_rules(self):
        result = prompts.get_implementation_prompt(cwd="/tmp/task")

        assert "Unicode superscripts" in result
        assert "tofu boxes" in result
        assert "completion frame" in result
        assert "final theorem" in result.lower()

    def test_get_implementation_prompt_validates_preset_and_quality(self):
        with pytest.raises(ValueError, match="preset"):
            prompts.get_implementation_prompt(preset="invalid_preset")

        with pytest.raises(ValueError, match="quality"):
            prompts.get_implementation_prompt(quality="ultra")


class TestGetRenderReviewPrompt:
    def test_get_render_review_prompt_is_phase3_only(self):
        result = prompts.get_render_review_prompt(cwd="/tmp/task")

        assert "Phase 3" in result
        assert "render review" in result.lower()
        assert "Do not write code" in result
        assert "Do not render or re-render" in result

    def test_get_render_review_prompt_validates_preset_and_quality(self):
        with pytest.raises(ValueError, match="preset"):
            prompts.get_render_review_prompt(preset="invalid_preset")

        with pytest.raises(ValueError, match="quality"):
            prompts.get_render_review_prompt(quality="ultra")


class TestGetPlanningPrompt:
    def test_get_planning_prompt_is_planning_only(self):
        result = prompts.get_planning_prompt()

        assert "规划阶段" in result
        assert "不写代码" in result
        assert "不渲染" in result
        assert "phase1_planning" in result
        assert "scene.py" not in result
        assert "manim -q" not in result

    def test_get_planning_prompt_validates_preset_and_quality(self):
        with pytest.raises(ValueError, match="preset"):
            prompts.get_planning_prompt(preset="invalid_preset")

        with pytest.raises(ValueError, match="quality"):
            prompts.get_planning_prompt(quality="ultra")

    def test_get_planning_prompt_segments_mode_mentions_segment_ids(self):
        result = prompts.get_planning_prompt(render_mode="segments")

        assert "segments/<beat_id>.mp4" in result
