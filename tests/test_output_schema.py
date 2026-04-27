"""Tests for manim_agent.schemas module (PipelineOutput Pydantic model).

覆盖：模型校验、序列化、output_format schema 生成。
"""

import pytest

from manim_agent.schemas import PhaseSchemaRegistry, PipelineOutput

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

    def test_rendered_segments_are_structured(self):
        m = PipelineOutput(
            video_output="/x.mp4",
            rendered_segments=[
                {
                    "beat_id": "beat_001",
                    "title": "Intro",
                    "order_index": 0,
                    "video_path": "segments/beat_001.mp4",
                    "duration_seconds": 5.5,
                }
            ],
        )

        assert m.rendered_segments[0].beat_id == "beat_001"
        assert m.rendered_segments[0].duration_seconds == 5.5


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
        schema = PhaseSchemaRegistry.output_format_schema("pipeline_output")
        assert isinstance(schema, dict)
        assert schema["type"] == "json_schema"

    def test_schema_has_valid_structure(self):
        """schema 包含有效的结构（properties 和 type）。"""
        schema = PhaseSchemaRegistry.output_format_schema("pipeline_output")
        inner = schema["schema"]
        assert "properties" in inner
        assert inner["type"] == "object"
        props = inner["properties"]
        assert "video_output" in props
        assert "scene_file" in props

    def test_schema_matches_installed_claude_agent_sdk_contract(self):
        """SDK forwards output_format['schema'] as --json-schema."""
        schema = PhaseSchemaRegistry.output_format_schema("phase1_planning")
        assert schema["type"] == "json_schema"
        assert "schema" in schema
        assert "json_schema" not in schema
        assert set(schema["schema"]["properties"]) == {"build_spec"}
        assert "$defs" not in schema["schema"]
        assert "$ref" not in str(schema["schema"])

    def test_schema_optionals_allow_null(self):
        """可选字段在 schema 中允许 null。"""
        schema = PhaseSchemaRegistry.output_format_schema("pipeline_output")
        props = schema["schema"]["properties"]
        for field in ("scene_file", "scene_class", "duration_seconds", "narration", "source_code"):
            assert field in props, f"Missing field: {field}"

    def test_narration_schema_mentions_simplified_chinese_default(self):
        """narration 字段描述要明确默认中文口播要求。"""
        schema = PhaseSchemaRegistry.output_format_schema("pipeline_output")
        narration = schema["schema"]["properties"]["narration"]
        assert "Simplified Chinese" in narration["description"]
