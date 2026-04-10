"""Tests for manim_agent.output_schema module (PipelineOutput Pydantic model).

覆盖：模型校验、from_text_markers 解析、序列化、output_format schema 生成。
"""

import pytest

# 导入目标模块（Phase 1 实现前会 ImportError —— 红灯）
from manim_agent.output_schema import PipelineOutput


# ── 模型创建与字段校验 ──────────────────────────────────────


class TestModelCreation:
    def test_required_field_only(self):
        """仅传必填字段 video_output，其余默认 None。"""
        m = PipelineOutput(video_output="/path/to/video.mp4")
        assert m.video_output == "/path/to/video.mp4"
        assert m.scene_file is None
        assert m.scene_class is None
        assert m.duration_seconds is None
        assert m.narration is None
        assert m.source_code is None

    def test_all_fields_populated(self):
        """所有字段都有值。"""
        m = PipelineOutput(
            video_output="/out/final.mp4",
            scene_file="scenes/fft.py",
            scene_class="FourierScene",
            duration_seconds=45.5,
            narration="傅里叶变换是...",
            source_code="from manim import *\n\nclass FourierScene(Scene): ...",
        )
        assert m.scene_file == "scenes/fft.py"
        assert m.scene_class == "FourierScene"
        assert m.duration_seconds == 45.5
        assert "傅里叶" in m.narration
        assert "class FourierScene" in m.source_code

    def test_video_output_empty_raises(self):
        """video_output 为空字符串时 ValidationError。"""
        with pytest.raises(Exception):  # Pydantic ValidationError
            PipelineOutput(video_output="")

    def test_video_output_whitespace_raises(self):
        """video_output 为纯空白时 ValidationError。"""
        with pytest.raises(Exception):
            PipelineOutput(video_output="   ")

    def test_duration_negative_raises(self):
        """duration_seconds 为负数时 ValidationError。"""
        with pytest.raises(Exception):
            PipelineOutput(video_output="/x.mp4", duration_seconds=-1)

    def test_duration_zero_ok(self):
        """duration_seconds = 0 是合法的。"""
        m = PipelineOutput(video_output="/x.mp4", duration_seconds=0)
        assert m.duration_seconds == 0


# ── from_text_markers 解析 ────────────────────────────────────


class TestFromTextMarkers:
    def test_basic_markers(self):
        """标准标记全部解析成功。"""
        text = (
            "渲染完成\n"
            "VIDEO_OUTPUT: /media/out.mp4\n"
            "SCENE_FILE: scenes/fourier.py\n"
            "SCENE_CLASS: FourierTransformScene\n"
            "DURATION: 30\n"
            "NARRATION: 傅里叶变换将信号分解为不同频率的正弦波之和。\n"
        )
        result = PipelineOutput.from_text_markers(text)
        assert isinstance(result, PipelineOutput)
        assert result.video_output == "/media/out.mp4"
        assert result.scene_file == "scenes/fourier.py"
        assert result.scene_class == "FourierTransformScene"
        assert result.duration_seconds == 30.0
        assert "正弦波" in result.narration

    def test_only_required_marker(self):
        """只有 VIDEO_OUTPUT 时也能解析，其余为 None。"""
        result = PipelineOutput.from_text_markers("VIDEO_OUTPUT: /a.mp4")
        assert result.video_output == "/a.mp4"
        assert result.scene_file is None
        assert result.scene_class is None
        assert result.duration_seconds is None
        assert result.narration is None

    def test_missing_video_output_raises(self):
        """缺少 VIDEO_OUTPUT 标记时抛 ValueError。"""
        with pytest.raises(ValueError, match="VIDEO_OUTPUT"):
            PipelineOutput.from_text_markers("SCENE_FILE: x.py")

    def test_empty_text_raises(self):
        """空文本抛 ValueError。"""
        with pytest.raises(ValueError, match="VIDEO_OUTPUT"):
            PipelineOutput.from_text_markers("")

    def test_takes_last_video_output(self):
        """多个 VIDEO_OUTPUT 取最后一个。"""
        text = (
            "VIDEO_OUTPUT: /tmp/a.mp4\n"
            "重试中...\n"
            "VIDEO_OUTPUT: /tmp/final.mp4\n"
        )
        result = PipelineOutput.from_text_markers(text)
        assert result.video_output == "/tmp/final.mp4"

    def test_ignores_unknown_prefixes(self):
        """未知前缀的行被静默忽略。"""
        text = (
            "UNKNOWN_KEY: value\n"
            "VIDEO_OUTPUT: /out.mp4\n"
            "RANDOM: data\n"
        )
        result = PipelineOutput.from_text_markers(text)
        assert result.video_output == "/out.mp4"

    def test_narration_multiline(self):
        """NARRATION 支持多行文本（直到下一个标记或结尾）。"""
        text = (
            "VIDEO_OUTPUT: /out.mp4\n"
            "NARRATION: 第一行解说词。\n"
            "第二行继续解说。\n"
            "第三行结束。\n"
            "DURATION: 20\n"
        )
        result = PipelineOutput.from_text_markers(text)
        assert "第一行" in result.narration
        assert "第二行" in result.narration
        assert "第三行" in result.narration
        # DURATION 应该独立于 NARRATION
        assert result.duration_seconds == 20.0

    def test_narration_none_when_absent(self):
        """无 NARRATION 标记时 narration 为 None。"""
        result = PipelineOutput.from_text_markers("VIDEO_OUTPUT: /x.mp4")
        assert result.narration is None

    def test_duration_none_when_absent(self):
        """无 DURATION 标记时 duration_seconds 为 None。"""
        result = PipelineOutput.from_text_markers("VIDEO_OUTPUT: /x.mp4")
        assert result.duration_seconds is None

    def test_scene_info_none_when_absent(self):
        """无 SCENE_FILE/SCENE_CLASS 标记时对应字段为 None。"""
        result = PipelineOutput.from_text_markers("VIDEO_OUTPUT: /x.mp4")
        assert result.scene_file is None
        assert result.scene_class is None


# ── 序列化 ─────────────────────────────────────────────────────


class TestSerialization:
    def test_model_dump(self):
        """model_dump() 输出正确字典。"""
        m = PipelineOutput(
            video_output="/out.mp4",
            scene_file="s.py",
            scene_class="MyScene",
            duration_seconds=10,
            narration="hello",
            source_code="code",
        )
        d = m.model_dump()
        assert d["video_output"] == "/out.mp4"
        assert d["scene_file"] == "s.py"
        assert d["narration"] == "hello"

    def test_model_dump_excludes_none_by_default(self):
        """model_dump() 默认包含 None 字段（Pydantic v2 默认行为）。"""
        m = PipelineOutput(video_output="/out.mp4")
        d = m.model_dump()
        assert "video_output" in d
        assert "scene_file" in d
        assert d["scene_file"] is None


# ── output_format schema ────────────────────────────────────────


class TestOutputFormatSchema:
    def test_schema_is_valid_dict(self):
        """output_format_schema() 返回合法 dict。"""
        schema = PipelineOutput.output_format_schema()
        assert isinstance(schema, dict)
        assert schema["type"] == "json_schema"

    def test_schema_requires_video_output(self):
        """schema 中 video_output 是 required。"""
        schema = PipelineOutput.output_format_schema()
        props = schema["json_schema"]["schema"]["properties"]
        required = schema["json_schema"]["schema"].get("required", [])
        assert "video_output" in required

    def test_schema_optionals_allow_null(self):
        """可选字段在 schema 中允许 null。"""
        schema = PipelineOutput.output_format_schema()
        props = schema["json_schema"]["schema"]["properties"]
        # 可选字段应为 ["string", "null"] 或类似
        for field in ("scene_file", "scene_class", "duration_seconds", "narration", "source_code"):
            assert field in props, f"Missing field: {field}"
