"""Pipeline 输出的 Pydantic 数据模型与解析工具。

定义 Claude Agent 完成视频生成后的结构化输出格式，
通过 output_format_schema() 提供 SDK 结构化输出 schema（主路径）。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class PipelineOutput(BaseModel):
    """经过验证的 pipeline 输出结果。

    来源：SDK ResultMessage.structured_output → model_validate()
    """

    video_output: str = Field(
        ...,
        description="渲染输出的 MP4 文件路径",
        min_length=1,
    )

    @field_validator("video_output")
    @classmethod
    def _video_output_must_be_non_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("video_output must not be blank")
        return v
    scene_file: str | None = Field(
        default=None,
        description="Manim 场景 .py 脚本路径",
    )
    scene_class: str | None = Field(
        default=None,
        description="Manim Scene 类名",
    )
    duration_seconds: float | None = Field(
        default=None,
        description="估算视频时长（秒）",
        ge=0,
    )
    narration: str | None = Field(
        default=None,
        description="Claude 生成的专业解说词，用于 TTS 语音合成",
    )
    source_code: str | None = Field(
        default=None,
        description="从 Write/Edit 工具捕获的 Manim Python 源码",
    )

    # ── SDK output_format schema ───────────────────────────────

    @staticmethod
    def output_format_schema() -> dict[str, Any]:
        """生成 ClaudeAgentOptions.output_format 所需的 JSON Schema。"""
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "pipeline_output",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "video_output": {
                            "type": "string",
                            "description": "Absolute or relative path to rendered MP4",
                            "minLength": 1,
                        },
                        "scene_file": {
                            "type": ["string", "null"],
                            "description": "Path to the Manim scene .py script",
                        },
                        "scene_class": {
                            "type": ["string", "null"],
                            "description": "Name of the Manim Scene class",
                        },
                        "duration_seconds": {
                            "type": ["number", "null"],
                            "description": "Estimated video duration in seconds",
                            "minimum": 0,
                        },
                        "narration": {
                            "type": ["string", "null"],
                            "description": "Professional narration script for TTS",
                        },
                        "source_code": {
                            "type": ["string", "null"],
                            "description": "Captured Manim Python source code",
                        },
                    },
                    "required": ["video_output"],
                    "additionalProperties": False,
                },
            },
        }
