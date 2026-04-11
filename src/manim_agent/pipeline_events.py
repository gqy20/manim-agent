"""结构化 Pipeline 事件类型系统。

定义 Claude Agent 执行过程中的所有事件类型，
支持工具调用生命周期、思考块、进度追踪等维度的调试信息。
事件通过 SSE 推送到前端 LogViewer 进行结构化渲染。
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ── 事件类型枚举 ─────────────────────────────────────────────


class EventType(str, Enum):
    """Pipeline 事件类型分类。"""

    LOG = "log"               # 纯文本日志行（向后兼容）
    STATUS = "status"           # 任务状态变更
    ERROR = "error"             # 错误事件
    TOOL_START = "tool_start"     # 工具调用开始
    TOOL_RESULT = "tool_result"   # 工具调用完成
    THINKING = "thinking"         # 思考/推理块
    PROGRESS = "progress"         # 进度追踪（token/轮次/耗时）


# ── 事件载荷模型 ──────────────────────────────────────────────


class ToolStartPayload(BaseModel):
    """工具调用开始时的上下文。"""

    tool_use_id: str = Field(..., description="SDK 工具调用唯一 ID")
    name: str = Field(..., description="工具名称 (Write/Bash/Edit/Read 等)")
    input_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="工具输入参数摘要",
    )


class ToolResultPayload(BaseModel):
    """工具调用结果。"""

    tool_use_id: str = Field(..., description="关联的 tool_start ID")
    name: str = Field(..., description="工具名称")
    is_error: bool = Field(False, description="是否执行失败")
    content: Optional[str] = Field(
        None,
        description="工具输出内容（成功时可能有值）",
    )
    duration_ms: Optional[int] = Field(
        None,
        description="工具执行耗时（毫秒）",
    )


class ThinkingPayload(BaseModel):
    """Claude 思考/推理块。"""

    thinking: str = Field(..., description="完整思考文本")
    preview: Optional[str] = Field(
        None,
        description="自动截断的预览（≤100 字符）",
    )
    signature: str = Field(default="", description="思考签名")


class ProgressPayload(BaseModel):
    """执行进度快照。"""

    turn: int = Field(..., description="当前交互轮次")
    total_tokens: int = Field(..., description="累计 token 消耗")
    tool_uses: int = Field(..., description="累计工具调用次数")
    elapsed_ms: int = Field(..., description="pipeline 已运行时间（毫秒）")
    last_tool_name: Optional[str] = Field(
        None,
        description="最近使用的工具名称",
    )

    @field_validator("elapsed_ms")
    @classmethod
    def _non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("elapsed_ms must be non-negative")
        return v


class StatusPayload(BaseModel):
    """Authoritative task/phase status emitted by the backend."""

    task_status: str = Field(..., description="Task lifecycle status")
    phase: Optional[str] = Field(default=None, description="Current pipeline phase id")
    message: Optional[str] = Field(default=None, description="Optional human-readable note")


# ── 统一事件模型 ──────────────────────────────────────────────


class PipelineEvent(BaseModel):
    """Pipeline 结构化事件。

    所有事件携带：
    - event_type: 分类枚举
    data: 类型化载荷（log 时为 str，其他为对应 Payload 模型）
    timestamp: ISO 8601 时间戳（自动生成或显式传入）

    序列化后兼容 SSEEvent 格式（event_type → type 别名）。
    """

    event_type: EventType
    data: (
        ToolStartPayload
        | ToolResultPayload
        | ThinkingPayload
        | ProgressPayload
        | StatusPayload
        | str
    )
    timestamp: str = Field(
        default_factory=lambda: time.strftime(
            "%Y-%m-%dT%H:%M:%S%z", time.localtime()
        ),
        description="事件产生时间 (ISO 8601)",
    )

    @field_validator("data", mode="before")
    @classmethod
    def _auto_truncate_thinking_preview(cls, v: Any, info) -> Any:
        """ThinkingPayload 的 preview 超长时自动截断到 100 字符。"""
        if isinstance(v, ThinkingPayload) and v.preview is None and len(v.thinking) > 100:
            v.preview = v.thinking[:97].replace("\n", " ") + "..."
        return v
