"""Tests for pipeline_narration module."""

import pytest


class TestLooksLikeSpokenNarration:
    """Tests for narration quality heuristic."""

    def test_short_text_rejected(self):
        from manim_agent.pipeline_narration import _looks_like_spoken_narration

        assert _looks_like_spoken_narration("你好") is False
        assert _looks_like_spoken_narration("") is False

    def test_instruction_style_rejected(self):
        from manim_agent.pipeline_narration import _looks_like_spoken_narration

        assert _looks_like_spoken_narration("请帮我制作一个动画") is False
        assert _looks_like_spoken_narration("请生成一段傅里叶变换的演示") is False

    def test_english_instruction_rejected(self):
        from manim_agent.pipeline_narration import _looks_like_spoken_narration

        assert _looks_like_spoken_narration("Create a Fourier transform animation") is False

    def test_title_only_rejected(self):
        from manim_agent.pipeline_narration import _looks_like_spoken_narration

        assert _looks_like_spoken_narration("傅里叶变换") is False
        assert _looks_like_spoken_narration("Test Topic") is False

    def test_genuine_narration_accepted(self):
        from manim_agent.pipeline_narration import _looks_like_spoken_narration

        text = "大家好，今天我们来学习傅里叶变换的原理。首先，我们可以看到..."
        assert _looks_like_spoken_narration(text) is True

    def test_multiple_spoken_markers_accepted(self):
        from manim_agent.pipeline_narration import _looks_like_spoken_narration

        text = "我们可以看到，这里首先需要注意，然后接下来..."
        assert _looks_like_spoken_narration(text) is True

    def test_long_text_accepted_without_markers(self):
        from manim_agent.pipeline_narration import _looks_like_spoken_narration

        text = "A" * 100
        assert _looks_like_spoken_narration(text) is True


class TestBuildTemplateNarration:
    """Tests for template-based narration fallback."""

    def test_single_beat(self):
        from manim_agent.pipeline_narration import _build_template_narration

        result = _build_template_narration(
            implemented_beats=["介绍概念"],
            beat_to_narration_map=[],
            user_topic="傅里叶变换",
        )
        assert "傅里叶变换" in result.narration
        assert "介绍概念" in result.narration
        assert result.generation_method == "template"

    def test_multiple_beats(self):
        from manim_agent.pipeline_narration import _build_template_narration

        result = _build_template_narration(
            implemented_beats=["第一部分", "第二部分", "第三部分"],
            beat_to_narration_map=[],
            user_topic="测试主题",
        )
        assert "第一部分" in result.narration
        assert "第二部分" in result.narration
        assert "第三部分" in result.narration
        assert len(result.beat_coverage) == 3

    def test_uses_beat_to_narration_map_when_available(self):
        from manim_agent.pipeline_narration import _build_template_narration

        result = _build_template_narration(
            implemented_beats=["Intro", "Main"],
            beat_to_narration_map=["欢迎大家", "核心内容"],
            user_topic="测试",
        )
        assert "欢迎大家" in result.narration
        assert "核心内容" in result.narration
        assert "Intro" not in result.narration
        assert result.beat_coverage == ["欢迎大家", "核心内容"]

    def test_opening_and_closing_phrases(self):
        from manim_agent.pipeline_narration import _build_template_narration

        result = _build_template_narration(
            implemented_beats=["内容"],
            beat_to_narration_map=[],
            user_topic="主题",
        )
        assert "大家好" in result.narration
        assert "谢谢大家" in result.narration or "观看" in result.narration

    def test_empty_beats_fallback(self):
        from manim_agent.pipeline_narration import _build_template_narration

        result = _build_template_narration(
            implemented_beats=[],
            beat_to_narration_map=[],
            user_topic="测试",
        )
        assert "测试" in result.narration
        assert result.char_count > 0
