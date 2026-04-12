"""Tests for manim_agent.prompts module."""

import pytest

from manim_agent import prompts


class TestSystemPrompt:
    def test_system_prompt_is_string(self):
        """SYSTEM_PROMPT 是非空字符串。"""
        assert isinstance(prompts.SYSTEM_PROMPT, str)
        assert len(prompts.SYSTEM_PROMPT) > 0

    def test_system_prompt_contains_role(self):
        """SYSTEM_PROMPT 包含角色定义。"""
        assert "Manim" in prompts.SYSTEM_PROMPT or "manim" in prompts.SYSTEM_PROMPT.lower()

    def test_system_prompt_contains_output_format(self):
        """SYSTEM_PROMPT 包含渲染输出相关指令。"""
        # 不再要求文本标记，prompt 应包含渲染/输出相关内容
        assert "render" in prompts.SYSTEM_PROMPT.lower() or "output" in prompts.SYSTEM_PROMPT.lower()

    def test_system_prompt_contains_workflow_rules(self):
        """SYSTEM_PROMPT 包含工作流程规则。"""
        # 至少包含渲染命令相关内容
        assert "manim" in prompts.SYSTEM_PROMPT.lower() or "render" in prompts.SYSTEM_PROMPT.lower()


    def test_system_prompt_mentions_manim_production_plugin(self):
        assert "manim-production" in prompts.SYSTEM_PROMPT


class TestGetPrompt:
    def test_get_prompt_default(self):
        """默认模式返回包含用户文本的完整 prompt。"""
        result = prompts.get_prompt("解释傅里叶变换")
        assert isinstance(result, str)
        assert "傅里叶变换" in result
        assert len(result) > len("解释傅里叶变换")

    def test_get_prompt_contains_system_prompt(self):
        """返回的 prompt 包含系统提示词内容。"""
        result = prompts.get_prompt("测试文本")
        # 系统提示词的关键片段应出现在结果中
        assert "render" in result.lower() or "output" in result.lower()

    def test_get_prompt_educational_preset(self):
        """educational 预设包含教学相关关键词。"""
        result = prompts.get_prompt("测试", preset="educational")
        assert "教学" in result or "循序渐进" in result or "教育" in result

    def test_get_prompt_presentation_preset(self):
        """presentation 预设包含演示相关关键词。"""
        result = prompts.get_prompt("测试", preset="presentation")
        assert "演示" in result or "简洁" in result or "汇报" in result

    def test_get_prompt_proof_preset(self):
        """proof 预设包含证明/推导相关关键词。"""
        result = prompts.get_prompt("测试", preset="proof")
        assert "证明" in result or "推导" in result or "逻辑" in result

    def test_get_prompt_concept_preset(self):
        """concept 预设包含可视化/概念相关关键词。"""
        result = prompts.get_prompt("测试", preset="concept")
        assert "可视化" in result or "直观" in result or "比喻" in result

    def test_get_prompt_invalid_preset_raises(self):
        """无效的 preset 抛出 ValueError。"""
        with pytest.raises(ValueError, match="preset"):
            prompts.get_prompt("测试", preset="invalid_preset")

    def test_get_prompt_quality_high(self):
        """high 质量使用 -qh 渲染参数。"""
        result = prompts.get_prompt("测试", quality="high")
        assert "-qh" in result

    def test_get_prompt_quality_medium(self):
        """medium 质量使用 -qm 渲染参数。"""
        result = prompts.get_prompt("测试", quality="medium")
        assert "-qm" in result

    def test_get_prompt_quality_low(self):
        """low 质量使用 -ql 渲染参数。"""
        result = prompts.get_prompt("测试", quality="low")
        assert "-ql" in result

    def test_get_prompt_quality_invalid_raises(self):
        """无效的 quality 抛出 ValueError。"""
        with pytest.raises(ValueError, match="quality"):
            prompts.get_prompt("测试", quality="ultra")

    def test_get_prompt_task_directory_instructions_include_chinese_narration(self):
        """任务目录模式会额外约束中文解说和固定文件名。"""
        result = prompts.get_prompt("测试", cwd="/tmp/task")
        assert "scene.py" in result
        assert "GeneratedScene" in result
        assert "Run Manim directly" in result
        assert "Simplified Chinese" in result
    def test_get_prompt_mentions_manim_production_plugin_when_task_directory_is_set(self):
        result = prompts.get_prompt("娴嬭瘯", cwd="/tmp/task")
        assert "manim-production" in result
