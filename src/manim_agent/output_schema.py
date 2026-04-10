"""Pipeline 输出的 Pydantic 数据模型与解析工具。

定义 Claude Agent 完成视频生成后的结构化输出格式，
提供 from_text_markers() 文本标记解析（fallback 路径）
和 output_format_schema() SDK 结构化输出 schema（主路径）。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class PipelineOutput(BaseModel):
    """经过验证的 pipeline 输出结果。

    来源有两条路径：
    1. **主路径**：SDK ResultMessage.structured_output → model_validate()
    2. **Fallback**：Claude 文本输出中的标记 → from_text_markers()
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

    # ── 文本标记解析 (fallback) ──────────────────────────────

    @classmethod
    def from_text_markers(cls, text: str) -> "PipelineOutput":
        """从 Claude 文本输出中解析结构化标记。

        支持的标记格式：
            VIDEO_OUTPUT: <path>
            SCENE_FILE: <path>
            SCENE_CLASS: <name>
            DURATION: <seconds>
            NARRATION: <多行解说词>

        Args:
            text: Claude 的文本输出（可能含多个 TextBlock 拼接）。

        Returns:
            验证通过的 PipelineOutput 实例。

        Raises:
            ValueError: 缺少必填的 VIDEO_OUTPUT 标记。
        """
        lines = text.splitlines()

        # 提取单值标记
        video_output: str | None = None
        scene_file: str | None = None
        scene_class: str | None = None
        duration_seconds: float | None = None
        narration: str | None = None

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            if line.startswith("VIDEO_OUTPUT:"):
                video_output = line.split(":", 1)[1].strip()
            elif line.startswith("SCENE_FILE:"):
                scene_file = line.split(":", 1)[1].strip()
            elif line.startswith("SCENE_CLASS:"):
                scene_class = line.split(":", 1)[1].strip()
            elif line.startswith("DURATION:"):
                try:
                    duration_seconds = float(line.split(":", 1)[1].strip())
                except ValueError:
                    pass  # 忽略非法值
            elif line.startswith("NARRATION:"):
                # 多行 narration：收集直到下一个标记或文本结尾
                header = line.split(":", 1)[1].strip()
                narr_parts = [header] if header else []
                i += 1
                while i < len(lines):
                    next_line = lines[i].strip()
                    # 遇到已知标记前缀则停止
                    if next_line.startswith((
                        "VIDEO_OUTPUT:", "SCENE_FILE:", "SCENE_CLASS:",
                        "DURATION:", "NARRATION:",
                    )):
                        i -= 1  # 回退，让外层循环处理这个标记
                        break
                    narr_parts.append(lines[i])  # 保留原始缩进
                    i += 1
                narration = "\n".join(narr_parts).strip() if narr_parts else None
                continue  # i 已经在正确位置

            i += 1

        if not video_output:
            raise ValueError(
                "Missing required VIDEO_OUTPUT marker in text output. "
                "The agent may have failed to render the scene."
            )

        return cls(
            video_output=video_output,
            scene_file=scene_file,
            scene_class=scene_class,
            duration_seconds=duration_seconds,
            narration=narration,
        )

    # ── SDK output_format schema ───────────────────────────────

    @staticmethod
    def output_format_schema() -> dict[str, Any]:
        """生成 ClaudeAgentOptions.output_format 所需的 JSON Schema。

        通过此 schema 要求 SDK/CLI 返回符合 PipelineOutput 结构的
        structured_output，避免脆弱的文本标记解析。
        """
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
