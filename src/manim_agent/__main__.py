"""CLI 入口：python -m manim_agent

解析命令行参数，编排 Claude Agent SDK → TTS → FFmpeg 的完整 pipeline。
充分利用 SDK 消息流中的 ToolUse / ToolResult / ResultMessage 等结构化信息，
提供实时工作日志输出。通过 session_id + fork_session 实现与本地 Claude Code 的会话隔离。
"""

import argparse
import asyncio
import functools
import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

load_dotenv()

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    HookContext,
    HookMatcher,
    Message,
    PostToolUseHookInput,
    RateLimitEvent,
    ResultMessage,
    StreamEvent,
    TaskNotificationMessage,
    TaskProgressMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    query,
)
from claude_agent_sdk.types import (
    PostToolUseHookSpecificOutput,
    SyncHookJSONOutput,
)

from . import prompts
from . import tts_client
from . import video_builder
from .output_schema import PipelineOutput
from .pipeline_events import (
    EventType,
    PipelineEvent,
    ThinkingPayload,
    ProgressPayload,
    ToolResultPayload,
    ToolStartPayload,
)


# ── Hook 回调：使用 SDK 原生 Hook 系统替代手动 ToolUseBlock 迭代 ───────


class _HookState:
    """Hook 共享状态，用于在多个 hook 调用间传递数据。"""

    def __init__(self) -> None:
        self.captured_source_code: dict[str, str] = {}
        self.event_callback: Callable[[PipelineEvent], None] | None = None


_hook_state = _HookState()


async def _on_post_tool_use(
    input_data: PostToolUseHookInput,
    tool_use_id: str | None,
    context: HookContext,
) -> SyncHookJSONOutput:
    """PostToolUse hook：捕获 Write/Edit 工具的源码。

    使用 SDK 原生 Hook 系统替代手动遍历 ToolUseBlock。

    盲区7: 使用 print 确保日志在所有日志级别可见（logger.debug 可能被过滤），
    同时记录完整的工具输入信息用于排查时序问题。
    """
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # ── 盲区7: 使用 print 替代 logger.debug，确保可见性 ──
    print(
        f"  [HOOK] PostToolUse: tool_name={tool_name!r}, "
        f"tool_use_id={tool_use_id!r}"
    )

    if tool_name in ("Write", "Edit") and isinstance(tool_input, dict):
        file_path = tool_input.get("file_path", "")
        content = tool_input.get("content", "")
        print(
            f"  [HOOK] PostToolUse: {tool_name} file_path={file_path!r}, "
            f"content_length={len(content) if content else 0}"
        )
        if file_path.endswith(".py") and content:
            _hook_state.captured_source_code[file_path] = content
            print(
                f"  [HOOK] Captured source: {file_path}, "
                f"total_files={len(_hook_state.captured_source_code)}"
            )
    else:
        # 记录被忽略的工具调用（可能发现意外的工具使用）
        if tool_name:
            print(f"  [HOOK] PostToolUse: skipping non-target tool: {tool_name}")

    return SyncHookJSONOutput(
        hookSpecificOutput=PostToolUseHookSpecificOutput(
            hookEventName="PostToolUse",
        )
    )


logger = logging.getLogger(__name__)


# ── 日志样式常量 ───────────────────────────────────────────────

_LOG_SEPARATOR = "═" * 58
_EMOJI = {
    "write": "\u270f\ufe0f",  # ✏️
    "bash": "\U0001f528",  # 🔨
    "read": "\U0001f4cf",  # 📸
    "think": "\U0001f4ad",  # 💭
    "video": "\U0001f3a5",  # 📤
    "check": "\u2705",  # ✅
    "cross": "\u274c",  # ❌
    "tts": "\U0001f3a4",  # 🎙️
    "film": "\U0001f3ac",  # 🎬
    "chart": "\U0001f4ca",  # 📊
    "gear": "\u2699\ufe0f",  # ⚙
}


# ── 消息分发器 ─────────────────────────────────────────────────


# ASCII-only console markers for Windows terminals with non-UTF-8 encodings.
_LOG_SEPARATOR = "=" * 58
_EMOJI = {
    "write": "[WRITE]",
    "bash": "[BASH]",
    "read": "[READ]",
    "think": "[THINK]",
    "video": "[VIDEO]",
    "check": "[OK]",
    "cross": "[ERR]",
    "tts": "[TTS]",
    "film": "[MUX]",
    "chart": "[SUMMARY]",
    "gear": "[PROGRESS]",
}


class _MessageDispatcher:
    """分发 query() 消息流中的各类消息，提取结构化信息并输出实时日志。

    利用 SDK 原生 Hook 系统（PostToolUseHookInput）捕获源码，
    使用 TaskNotificationMessage.output_file 获取视频输出路径，
    直接使用 ResultMessage 原生字段替代手动构建 result_summary。
    """

    def __init__(
        self,
        verbose: bool = True,
        log_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.verbose = verbose
        self.log_callback = log_callback
        self.event_callback: Callable[[PipelineEvent], None] | None = None
        self.turn_count = 0
        self.tool_use_count = 0
        self.tool_stats: dict[str, int] = {}
        self.collected_text: list[str] = []
        # ── 消息统计（调试用）──
        self._msg_count: int = 0
        self._msg_type_stats: dict[str, int] = {}
        self._assistant_msg_count: int = 0
        # ── PipelineOutput ──
        self.pipeline_output: PipelineOutput | None = None
        # ── 视频输出路径（从 TaskNotificationMessage.output_file 获取）──
        self.video_output: str | None = None
        # ── 向后兼容的旧属性 ──
        self.scene_file: str | None = None
        self.scene_class: str | None = None
        # ── 直接使用 ResultMessage 原生字段，不再手动构建 ──

    # ── 公共接口 ──────────────────────────────────────────────

    def dispatch(self, message: Message) -> None:
        """根据消息类型路由到对应处理器。"""
        # ── 消息计数（盲区1：审计消息完整性）──
        self._msg_count += 1
        msg_type = type(message).__name__
        self._msg_type_stats[msg_type] = self._msg_type_stats.get(msg_type, 0) + 1
        self._print(f"  [DEBUG] dispatch #{self._msg_count}: {msg_type}")

        if isinstance(message, AssistantMessage):
            self._handle_assistant(message)
        elif isinstance(message, ResultMessage):
            self._handle_result(message)
        elif isinstance(message, RateLimitEvent):
            self._handle_rate_limit(message)
        elif isinstance(message, TaskProgressMessage):
            self._handle_task_progress(message)
        elif isinstance(message, TaskNotificationMessage):
            self._handle_task_notification(message)
        elif isinstance(message, StreamEvent):
            self._handle_stream_event(message)
        else:
            # 未识别的消息类型（盲区1补充：防止静默丢弃）
            self._print(f"  [DEBUG] dispatch: unhandled message type: {msg_type}, "
                        f"attrs={dir(message)}")

    def get_pipeline_output(self) -> PipelineOutput | None:
        """返回验证后的 PipelineOutput（可能为 None）。

        优先级：structured_output > Hook 捕获源码 > None
        """
        self._print(
            f"  [DEBUG] get_pipeline_output: self.pipeline_output is {'not None' if self.pipeline_output is not None else 'None'}"
        )
        if self.pipeline_output is not None:
            self._print(
                f"  [DEBUG] get_pipeline_output: returning cached PipelineOutput, video_output={self.pipeline_output.video_output!r}"
            )
            return self.pipeline_output
        # fallback：从 collected_text 的标记中解析
        self._print(
            f"  [DEBUG] get_pipeline_output: trying text markers fallback, collected_text length={len(self.collected_text)}"
        )
        try:
            self.pipeline_output = PipelineOutput.from_text_markers("\n".join(self.collected_text))
            self._print(
                f"  [DEBUG] get_pipeline_output: text markers parsed, video_output={self.pipeline_output.video_output!r}"
            )
        except (ValueError, Exception) as e:
            self._print(f"  [DEBUG] get_pipeline_output: text markers failed: {e}")
            return None
        # 关联 Hook 捕获的源代码
        if (
            self.pipeline_output.scene_file
            and self.pipeline_output.scene_file in _hook_state.captured_source_code
        ):
            self.pipeline_output.source_code = _hook_state.captured_source_code[
                self.pipeline_output.scene_file
            ]
            self._print(f"  [DEBUG] get_pipeline_output: source code linked from hook state")
        else:
            self._print(
                f"  [DEBUG] get_pipeline_output: scene_file={self.pipeline_output.scene_file!r}, hook captured keys={list(_hook_state.captured_source_code.keys())}"
            )
        # 同步向后兼容属性
        self._sync_compat_attrs()
        return self.pipeline_output

    def get_video_output(self) -> str | None:
        """返回提取到的视频输出路径（向后兼容接口）。"""
        po = self.get_pipeline_output()
        return po.video_output if po else None

    # ── 消息处理器 ──────────────────────────────────────────────

    def _handle_assistant(self, msg: AssistantMessage) -> None:
        """处理 AssistantMessage，遍历所有 content block。

        注意：源码捕获已移至 SDK Hook 系统（PostToolUseHookInput）。
        """
        self._assistant_msg_count += 1
        # ── 盲区2: stop_reason 是判断 Agent 行为的关键字段 ──
        self._print(
            f"  [DEBUG] _handle_assistant #{self._assistant_msg_count}: "
            f"stop_reason={msg.stop_reason!r}, model={msg.model!r}, "
            f"error={msg.error!r}, blocks={len(msg.content)}, "
            f"message_id={msg.message_id!r}"
        )
        for block in msg.content:
            if isinstance(block, TextBlock):
                self._log_text(block.text)
                self.collected_text.append(block.text)

            elif isinstance(block, ToolUseBlock):
                self._log_tool_use(block)
                self.tool_use_count += 1
                name = block.name
                self.tool_stats[name] = self.tool_stats.get(name, 0) + 1
                if name in ("Write", "Edit"):
                    self._print(
                        f"  [DEBUG] _handle_assistant: {name} tool called (hook will capture source)"
                    )

            elif isinstance(block, ToolResultBlock):
                self._log_tool_result(block)

            elif isinstance(block, ThinkingBlock):
                self._log_thinking(block)

    def _handle_result(self, msg: ResultMessage) -> None:
        """处理 ResultMessage，记录会话摘要并尝试解析 structured_output。

        直接使用 ResultMessage 原生字段，通过 result_summary property 提供向后兼容访问。
        """
        self._result_message = msg
        # ── 盲区4: ResultMessage 全字段记录 ──
        self._print(
            f"  [DEBUG] _handle_result: === RESULT MESSAGE FULL DUMP ==="
        )
        self._print(
            f"  [DEBUG] _handle_result: stop_reason={msg.stop_reason!r}, "
            f"is_error={msg.is_error}, num_turns={msg.num_turns}"
        )
        self._print(
            f"  [DEBUG] _handle_result: duration_ms={msg.duration_ms}, "
            f"duration_api_ms={msg.duration_api_ms}"
        )
        self._print(
            f"  [DEBUG] _handle_result: session_id={msg.session_id!r}, "
            f"uuid={msg.uuid!r}"
        )
        if msg.total_cost_usd is not None:
            self._print(f"  [DEBUG] _handle_result: total_cost_usd={msg.total_cost_usd}")
        if msg.usage:
            self._print(f"  [DEBUG] _handle_result: usage={msg.usage}")
        if msg.model_usage:
            self._print(f"  [DEBUG] _handle_result: model_usage={msg.model_usage}")
        if msg.errors:
            self._print(f"  [DEBUG] _handle_result: ERRORS={msg.errors}")
        if msg.permission_denials:
            self._print(
                f"  [DEBUG] _handle_result: PERMISSION_DENIALS={msg.permission_denials}"
            )
        if msg.result:
            preview = str(msg.result)[:300]
            self._print(f"  [DEBUG] _handle_result: result (preview)={preview!r}")
        # structured_output
        self._print(
            f"  [DEBUG] _handle_result: structured_output is "
            f"{'not None' if msg.structured_output is not None else 'None'}"
        )
        if msg.structured_output is not None:
            self._print(
                f"  [DEBUG] _handle_result: structured_output type="
                f"{type(msg.structured_output).__name__}, "
                f"value={str(msg.structured_output)[:500]!r}"
            )
        # ── 尝试从 structured_output 构建 PipelineOutput（主路径）──
        if msg.structured_output is not None:
            try:
                raw = msg.structured_output
                self._print(f"  [DEBUG] _handle_result: raw type={type(raw).__name__}")
                # 类型归一化：SDK 可能返回 str/dict/其他类型
                if isinstance(raw, str):
                    raw = json.loads(raw)
                    self._print(f"  [DEBUG] _handle_result: parsed JSON, type={type(raw).__name__}")
                if not isinstance(raw, dict):
                    raise ValueError(f"structured_output unexpected type: {type(raw).__name__}")
                self.pipeline_output = PipelineOutput.model_validate(raw)
                self._print(
                    f"  [DEBUG] _handle_result: PipelineOutput validated, video_output={self.pipeline_output.video_output!r}"
                )
                # 关联 Hook 捕获的源代码
                if (
                    self.pipeline_output.scene_file
                    and self.pipeline_output.scene_file in _hook_state.captured_source_code
                ):
                    self.pipeline_output.source_code = _hook_state.captured_source_code[
                        self.pipeline_output.scene_file
                    ]
                    self._print(
                        f"  [DEBUG] _handle_result: source code linked for {self.pipeline_output.scene_file}"
                    )
                self._sync_compat_attrs()
            except Exception as e:
                logger.warning(
                    "structured_output validation failed, falling back to text markers: %s", e
                )
                self._print(f"  [DEBUG] _handle_result: validation failed: {e}")
        else:
            self._print(
                f"  [DEBUG] _handle_result: no structured_output, will try text markers fallback"
            )
        self._log_result_summary()

    @property
    def result_summary(self) -> dict[str, Any] | None:
        """返回 ResultMessage 字段的字典视图（向后兼容）。"""
        if not hasattr(self, "_result_message") or self._result_message is None:
            return None
        msg = self._result_message
        return {
            "turns": msg.num_turns,
            "cost_usd": msg.total_cost_usd,
            "duration_ms": msg.duration_ms,
            "is_error": msg.is_error,
            "stop_reason": msg.stop_reason,
            "errors": msg.errors,
        }

    def _handle_rate_limit(self, event: RateLimitEvent) -> None:
        """处理限流事件。"""
        info = event.rate_limit_info
        status_icon = _EMOJI["check"] if info.status == "allowed" else _EMOJI["cross"]
        self._print(
            f"  {status_icon} RateLimit: {info.status} (utilization={info.utilization:.0%})"
        )

    def _handle_task_progress(self, msg: TaskProgressMessage) -> None:
        """处理任务进度消息 + 发射 PROGRESS 结构化事件。"""
        usage = msg.usage
        self._print(
            f"  {_EMOJI['gear']} Progress: "
            f"{usage['total_tokens']} tokens, "
            f"{usage['tool_uses']} tool_uses, "
            f"{usage['duration_ms'] // 1000}s"
        )
        # 发射结构化事件
        self.turn_count += 1
        self._emit_event(
            PipelineEvent(
                event_type=EventType.PROGRESS,
                data=ProgressPayload(
                    turn=self.turn_count,
                    total_tokens=usage["total_tokens"],
                    tool_uses=usage["tool_uses"],
                    elapsed_ms=usage["duration_ms"],
                    last_tool_name=None,
                ),
            )
        )

    def _handle_task_notification(self, msg: TaskNotificationMessage) -> None:
        """处理任务完成/失败通知。

        使用 SDK 原生的 TaskNotificationMessage.output_file 获取视频路径，
        无需解析文本标记。
        """
        icon = _EMOJI["check"] if msg.status == "completed" else _EMOJI["cross"]
        self._print(f"  {icon} Task {msg.status}: {msg.summary}")
        self._print(
            f"  [DEBUG] _handle_task_notification: output_file={msg.output_file!r}, status={msg.status}"
        )
        # 从 TaskNotificationMessage.output_file 获取视频输出路径
        if msg.status == "completed" and msg.output_file:
            self.video_output = msg.output_file
            self._print(
                f"  {_EMOJI['video']} Video output from task_notification: {msg.output_file}"
            )
        elif msg.status == "completed" and not msg.output_file:
            self._print(f"  [DEBUG] _handle_task_notification: completed but no output_file")

    def _handle_stream_event(self, msg: StreamEvent) -> None:
        """处理流式事件（token 级别的 API 增量更新）。

        StreamEvent.event 包含原始 Anthropic API 流事件，
        提取关键信息用于实时日志展示。
        """
        event = msg.event
        event_type_raw = event.get("type", "unknown") if isinstance(event, dict) else str(event)

        if event_type_raw == "content_block_delta":
            delta = event.get("delta", {}) if isinstance(event, dict) else {}
            if isinstance(delta, dict):
                delta_type = delta.get("type", "")
                if delta_type == "text_delta":
                    text = delta.get("text", "")
                    preview = text[:120].replace("\n", "\\n")
                    self._print(f"  {_EMOJI['think']} [STREAM] {preview}")
                elif delta_type == "thinking_delta":
                    thinking = delta.get("thinking", "")
                    preview = thinking[:120].replace("\n", "\\n")
                    self._print(f"  {_EMOJI['think']} [THINK-DELTA] {preview}")
                else:
                    self._print(f"  {_EMOJI['gear']} [{event_type_raw}] {delta_type}")
            elif isinstance(delta, str):
                # delta 有时是原始字符串
                self._print(f"  {_EMOJI['think']} [STREAM-DELTA] {delta[:120]}")
            else:
                self._print(f"  {_EMOJI['gear']} [{event_type_raw}] {delta}")
        elif event_type_raw == "message_start":
            self._print(f"  {_EMOJI['gear']} [STREAM] Message start")
        elif event_type_raw == "message_stop":
            self._print(f"  {_EMOJI['gear']} [STREAM] Message complete")
        else:
            self._print(f"  {_EMOJI['gear']} [STREAM] {event_type_raw}")

    # ── 内部辅助 ───────────────────────────────────────────────

    def _sync_compat_attrs(self) -> None:
        """将 pipeline_output 的值同步到向后兼容的旧属性。"""
        if self.pipeline_output is not None:
            self.video_output = self.pipeline_output.video_output
            self.scene_file = self.pipeline_output.scene_file
            self.scene_class = self.pipeline_output.scene_class

    def _emit_event(self, event: PipelineEvent) -> None:
        """通过 event_callback 发射结构化事件（如已注册）。"""
        if self.event_callback is not None:
            self.event_callback(event)

    # ── 日志格式化方法 ──────────────────────────────────────────

    def _log_text(self, text: str) -> None:
        """记录文本内容（通常不逐行打印，避免噪音）。"""
        pass  # 文本已收集到 collected_text，不需要逐行打印

    def _log_tool_use(self, block: ToolUseBlock) -> None:
        """打印工具调用信息 + 发射 TOOL_START 结构化事件。"""
        icon = _EMOJI.get(block.name.lower(), "\u25b6")
        input_summary = self._summarize_input(block.input)
        self._print(f"  {icon} {block.name} \u2192 {input_summary}")
        self._print(f"  [DEBUG] _log_tool_use: id={block.id}, name={block.name}")
        # 发射结构化事件
        self._emit_event(
            PipelineEvent(
                event_type=EventType.TOOL_START,
                data=ToolStartPayload(
                    tool_use_id=block.id,
                    name=block.name,
                    input_summary=block.input if isinstance(block.input, dict) else {},
                ),
            )
        )

    def _log_tool_result(self, block: ToolResultBlock) -> None:
        """打印工具执行结果 + 发射 TOOL_RESULT 结构化事件。

        盲区3: 对 Bash 工具打印完整输出，便于排查渲染失败原因。
        """
        content = block.content
        content_preview = ""
        if content:
            if isinstance(content, str):
                content_preview = content[:100].replace("\n", "\\n")
                # ── 盲区3: Bash 工具完整输出 ──
                # 通过 tool_use_id 关联之前的 ToolUseBlock 获取工具名
                # 这里打印完整内容以便排查渲染错误
                full_content = content.replace("\n", "\\n")
                if len(full_content) > 500:
                    self._print(
                        f"  [DEBUG] _log_tool_result: tool_use_id={block.tool_use_id}, "
                        f"is_error={block.is_error}, content_length={len(content)}"
                    )
                    self._print(
                        f"  [DEBUG] _log_tool_result: FULL CONTENT (first 1000):\n"
                        f"{full_content[:1000]}"
                    )
                    if len(full_content) > 1000:
                        self._print(
                            f"  [DEBUG] _log_tool_result: ... (truncated, total {len(content)} chars)"
                        )
                else:
                    self._print(
                        f"  [DEBUG] _log_tool_result: tool_use_id={block.tool_use_id}, "
                        f"is_error={block.is_error}, content={full_content!r}"
                    )
            elif isinstance(content, list):
                content_preview = f"list[{len(content)}]"
                # 多部分结果（stdout + stderr 分离时）
                self._print(
                    f"  [DEBUG] _log_tool_result: tool_use_id={block.tool_use_id}, "
                    f"is_error={block.is_error}, content_parts={len(content)}"
                )
                for i, part in enumerate(content):
                    part_str = str(part)
                    preview = part_str[:300].replace("\n", "\\n")
                    self._print(
                        f"  [DEBUG] _log_tool_result:   part[{i}] type="
                        f"{type(part).__name__}, preview={preview!r}"
                    )
                    if len(part_str) > 300:
                        self._print(
                            f"  [DEBUG] _log_tool_result:   part[{i}] ... "
                            f"(total {len(part_str)} chars)"
                        )
        else:
            self._print(
                f"  [DEBUG] _log_tool_result: tool_use_id={block.tool_use_id}, "
                f"is_error={block.is_error}, content=None/empty"
            )

        if block.is_error:
            self._print(f"  {_EMOJI['cross']} Result Error (tool_use_id={block.tool_use_id})")
        # 发射结构化事件
        self._emit_event(
            PipelineEvent(
                event_type=EventType.TOOL_RESULT,
                data=ToolResultPayload(
                    tool_use_id=block.tool_use_id,
                    name="",  # 名称从 tool_start 配对获取
                    is_error=block.is_error,
                    content=block.content if not block.is_error else None,
                    duration_ms=None,
                ),
            )
        )

    def _log_thinking(self, block: ThinkingBlock) -> None:
        """打印思考过程摘要 + 发射 THINKING 结构化事件。"""
        preview = block.thinking[:80].replace("\n", " ")
        if len(block.thinking) > 80:
            preview += "..."
        self._print(f"  {_EMOJI['think']} {preview}")
        # 发射结构化事件
        self._emit_event(
            PipelineEvent(
                event_type=EventType.THINKING,
                data=ThinkingPayload(
                    thinking=block.thinking,
                    signature=getattr(block, "signature", ""),
                ),
            )
        )

    def _log_result_summary(self) -> None:
        """打印会话摘要。"""
        s = self.result_summary
        if not s:
            return

        self._print("")
        self._print(f"{_LOG_SEPARATOR}")
        self._print(f"{_EMOJI['chart']} Session Summary:")
        self._print(
            f"  Turns: {s['turns']} | "
            f"Cost: ${s['cost_usd']:.4f} | "
            f"Duration: {s['duration_ms'] // 1000}s"
        )
        if self.tool_stats:
            tools_str = ", ".join(f"{k}\u00d7{v}" for k, v in self.tool_stats.items())
            self._print(f"  Tool calls: {self.tool_use_count} ({tools_str})")

        status_icon = _EMOJI["check"] if not s["is_error"] else _EMOJI["cross"]
        reason = f" ({s['stop_reason']})" if s.get("stop_reason") else ""
        errors = f" | Errors: {s['errors']}" if s.get("errors") else ""
        self._print(f"  Status: {status_icon}{reason}{errors}")
        self._print(_LOG_SEPARATOR)

    @staticmethod
    def _summarize_input(input_dict: dict[str, Any], max_len: int = 60) -> str:
        """将工具输入字典摘要为一行字符串。"""
        if not input_dict:
            return "{}"
        parts = []
        for k, v in input_dict.items():
            v_str = repr(v)
            if len(v_str) > max_len:
                v_str = v_str[: max_len - 3] + "..."
            parts.append(f"{k}={v_str}")
        result = " ".join(parts)
        if len(result) > max_len:
            result = result[: max_len - 3] + "..."
        return result

    def _print(self, message: str) -> None:
        """条件打印：verbose=True 时输出；同时调用回调（如有）。"""
        if self.verbose:
            try:
                print(message)
            except UnicodeEncodeError:
                print(message.encode("ascii", "replace").decode("ascii"))
        if self.log_callback:
            self.log_callback(message)


# ── CLI 参数解析 ──────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。

    Args:
        argv: 参数列表（默认为 sys.argv[1:]）。

    Returns:
        解析后的命名空间。
    """
    parser = argparse.ArgumentParser(
        prog="manim_agent",
        description="AI 驱动的 Manim 数学动画视频自动生成系统",
    )
    parser.add_argument(
        "text",
        help="自然语言描述的视频内容",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="output.mp4",
        help="输出视频文件路径 (default: output.mp4)",
    )
    parser.add_argument(
        "--voice",
        default="female-tianmei",
        help="MiniMax 音色 ID (default: female-tianmei)",
    )
    parser.add_argument(
        "--model",
        default="speech-2.8-hd",
        help="TTS 模型名称 (default: speech-2.8-hd)",
    )
    parser.add_argument(
        "--quality",
        choices=["high", "medium", "low"],
        default="high",
        help="渲染质量 (default: high)",
    )
    parser.add_argument(
        "--no-tts",
        action="store_true",
        help="跳过语音合成，只生成静音视频",
    )
    parser.add_argument(
        "--cwd",
        default=".",
        help="工作目录 (default: 当前目录)",
    )
    parser.add_argument(
        "--prompt-file",
        default=None,
        help="从文件读取自定义提示词",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=50,
        help="Claude 最大交互轮次 (default: 50)",
    )

    return parser.parse_args(argv)


# ── 结果提取（兼容接口） ──────────────────────────────────────


def extract_result(text: str) -> dict[str, str | None]:
    """从 Claude 输出文本中提取结构化结果标记（向后兼容接口）。

    Args:
        text: Claude 输出的文本内容（可能包含多行）。

    Returns:
        包含 video_output_path, scene_file, scene_class 的字典。
    """
    try:
        po = PipelineOutput.from_text_markers(text)
        return {
            "video_output_path": po.video_output,
            "scene_file": po.scene_file,
            "scene_class": po.scene_class,
        }
    except ValueError:
        return {
            "video_output_path": None,
            "scene_file": None,
            "scene_class": None,
        }


# ── Options 构建 ────────────────────────────────────────────────


def _stderr_handler(
    line: str,
    *,
    log_callback: Callable[[str], None] | None = None,
) -> None:
    """将 CLI 子进程的 stderr 输出转发到终端和可选的 SSE 回调。

    所有行都通过 log_callback 推送到前端（如果提供），
    error/warning 行额外标记以便前端高亮。
    """
    stripped = line.strip()
    # 始终推送到 SSE（让前端决定如何展示）
    if log_callback is not None:
        log_callback(f"[CLI] {stripped}")
    # error/warning 行同时输出到 stderr 以便终端开发者可见
    lower = line.lower()
    if any(kw in lower for kw in ("error", "warning", "fail", "exception")):
        print(f"  {_EMOJI['cross']} [CLI] {stripped}", file=sys.stderr)


def _build_options(
    cwd: str,
    system_prompt: str | None,
    max_turns: int,
    prompt_file: str | None = None,
    quality: str = "high",
    log_callback: Callable[[str], None] | None = None,
) -> ClaudeAgentOptions:
    """构建 ClaudeAgentOptions，含会话隔离和日志回调。

    Args:
        cwd: 工作目录。
        system_prompt: 系统提示词（优先级最高，若提供则直接使用）。
        max_turns: 最大交互轮次。
        prompt_file: 自定义提示词文件路径。
        quality: 渲染质量 ("high" | "medium" | "low")，
            仅在未提供 system_prompt 和 prompt_file 时生效。
        log_callback: 可选的日志回调，用于 SSE 推送。

    Returns:
        配置好的 options 对象。
    """
    # 加载系统提示词
    if prompt_file and Path(prompt_file).exists():
        final_system_prompt = Path(prompt_file).read_text(encoding="utf-8")
    elif system_prompt:
        final_system_prompt = system_prompt
    else:
        # 使用 prompts 模块构建含 quality 映射的完整提示词
        final_system_prompt = prompts.SYSTEM_PROMPT.replace(
            "-qh", prompts.QUALITY_FLAGS.get(quality, "-qh")
        )

    # 绑定 stderr 回调（将 CLI 输出推送到 SSE）
    bound_stderr = functools.partial(_stderr_handler, log_callback=log_callback)

    # ── 确保 Claude CLI 子进程能找到 manim ──
    # 继承当前环境变量，但确保 .venv\Scripts 在 PATH 中
    venv_scripts = str(Path(__file__).parent.parent.parent / ".venv" / "Scripts")
    current_path = os.environ.get("PATH", "")
    path_parts = [p for p in current_path.split(os.pathsep) if p]
    if venv_scripts not in path_parts:
        path_parts.append(venv_scripts)
    venv_env = {
        "PATH": os.pathsep.join(path_parts),
    }

    # ── 配置 SDK Hook 系统用于源码捕获 ──
    hooks = {
        "PostToolUse": [
            HookMatcher(
                matcher="Write|Edit",
                hooks=[_on_post_tool_use],
            ),
        ],
    }

    options = ClaudeAgentOptions(
        cwd=cwd,
        system_prompt=final_system_prompt,
        permission_mode="bypassPermissions",
        max_turns=max_turns,
        # ── 会话隔离：每次运行使用唯一 session ID，不污染用户本地 Claude Code ──
        session_id=str(uuid.uuid4()),
        fork_session=True,
        # ── 日志回调 ──
        stderr=bound_stderr,
        # ── 结构化输出 schema ──
        output_format=PipelineOutput.output_format_schema(),
        # ── 工具白名单：收敛攻击面，仅允许 pipeline 必需的工具（参照 Distill）──
        allowed_tools=[
            "Read",
            "Write",
            "Edit",
            "Bash",
            "Glob",
            "Grep",
        ],
        # ── 环境变量：确保 manim 可被 Claude CLI 找到 ──
        env=venv_env,
        # ── SDK Hook 系统：替代手动 ToolUseBlock 迭代 ──
        hooks=hooks,
        # ── 启用文件检查点以支持 rewind_files ──
        enable_file_checkpointing=True,
    )

    # ── 盲区6: 记录 CLI 关键配置参数 ──
    logger.debug(
        "_build_options: cwd=%s, max_turns=%s, permission_mode=%s, "
        "allowed_tools=%s, output_format=%s, fork_session=%s, "
        "enable_file_checkpointing%s, hooks=%s, system_prompt_length=%d",
        options.cwd,
        options.max_turns,
        options.permission_mode,
        options.allowed_tools,
        "set" if options.output_format else "None",
        options.fork_session,
        options.enable_file_checkpointing,
        list(options.hooks.keys()) if options.hooks else [],
        len(final_system_prompt) if final_system_prompt else 0,
    )
    print(
        f"  [DEBUG] _build_options: cwd={cwd}, max_turns={max_turns}, "
        f"permission_mode=bypassPermissions, "
        f"allowed_tools={options.allowed_tools}, "
        f"output_format={'set' if options.output_format else 'None'}, "
        f"system_prompt_len={len(final_system_prompt) if final_system_prompt else 0}"
    )

    return options


# ── Pipeline 编排 ─────────────────────────────────────────────


async def run_pipeline(
    user_text: str,
    output_path: str,
    voice_id: str = "female-tianmei",
    model: str = "speech-2.8-hd",
    quality: str = "high",
    no_tts: bool = False,
    cwd: str = ".",
    prompt_file: str | None = None,
    max_turns: int = 50,
    log_callback: Callable[[str], None] | None = None,
    preset: str = "default",
    _dispatcher_ref: list[Any] | None = None,
    event_callback: Callable[[PipelineEvent], None] | None = None,
) -> str:
    """执行完整的视频生成 pipeline。

    流程：
    1. 构建提示词和 options（含会话隔离）
    2. 调用 Claude Agent SDK (query)，通过 dispatcher 消费消息流
    3. 从 dispatcher 中提取 VIDEO_OUTPUT 路径
    4. （可选）TTS 语音合成
    5. （可选）FFmpeg 视频合成
    6. 返回最终视频路径

    Args:
        user_text: 用户输入的自然语言描述。
        output_path: 输出视频路径。
        voice_id: TTS 音色 ID。
        model: TTS 模型。
        quality: 渲染质量。
        no_tts: 是否跳过 TTS。
        cwd: 工作目录。
        prompt_file: 自定义提示词文件路径。
        max_turns: Claude 最大交互轮次。

    Returns:
        最终视频文件路径。

    Raises:
        RuntimeError: Claude 未输出 VIDEO_OUTPUT 标记。
    """
    # 1. 构建 options（含会话隔离 + quality + preset 映射）
    # 使用 prompts.get_prompt() 将 preset 后缀追加到系统提示词
    full_system_prompt = prompts.get_prompt(
        user_text="",  # 用户文本单独作为 query prompt 传入
        preset=preset,
        quality=quality,
    )
    # 去掉 get_prompt 追加的 "# 用户需求" 段落，只保留系统提示词部分
    system_prompt = full_system_prompt.rsplit("\n\n# 用户需求", 1)[0]

    options = _build_options(
        cwd=cwd,
        system_prompt=system_prompt,
        max_turns=max_turns,
        prompt_file=prompt_file,
        quality=quality,
        log_callback=log_callback,
    )

    # 用户提示词直接传递
    user_prompt = user_text

    # 2. 创建 dispatcher 并消费消息流
    dispatcher = _MessageDispatcher(verbose=True, log_callback=log_callback)
    if event_callback is not None:
        dispatcher.event_callback = event_callback
        _hook_state.event_callback = event_callback
    # ── 阶段标记：初始化完成，即将启动 SDK query ──
    dispatcher._print(f"\n{_LOG_SEPARATOR}")
    dispatcher._print(
        f"  Claude Agent 工作日志                              Session: {options.session_id[:8]}..."
    )
    dispatcher._print(_LOG_SEPARATOR)
    dispatcher._print(f"  {_EMOJI['gear']} Phase 1/4: 启动 Claude Agent SDK...")
    dispatcher._print(f"  quality={quality} preset={preset} max_turns={max_turns}")

    # ── Transport 层调试：通过包装 query() 捕获进程退出信息 ──
    # 使用 contextlib.wrap 或直接 patch SDK 内部 client 来拦截 close() 阶段
    import contextlib as _ctx

    # 统计 CLI stderr 行数（通过包装 log_callback）
    _cli_stderr_lines: list[str] = []
    _orig_log_callback = log_callback

    def _counting_log_callback(line: str) -> None:
        _cli_stderr_lines.append(line)
        if _orig_log_callback:
            _orig_log_callback(line)

    # 用带计数的回调临时替换 options.stderr（仅用于本次调用）
    _saved_stderr = options.stderr
    options.stderr = _counting_log_callback

    # ── 查询循环：捕获 SDK 层面的任何异常 ──
    _sdk_exception: BaseException | None = None
    try:
        async for message in query(prompt=user_prompt, options=options):
            dispatcher.dispatch(message)
    except Exception as exc:
        _sdk_exception = exc
        dispatcher._print(f"  [DEBUG] run_pipeline: === SDK QUERY LOOP EXCEPTION ===")
        dispatcher._print(f"  [DEBUG] run_pipeline: exception type={type(exc).__name__}")
        dispatcher._print(f"  [DEBUG] run_pipeline: exception message={exc}")
        import traceback as _tb
        for _line in _tb.format_exception(type(exc), exc, exc.__traceback__):
            for _ll in _line.rstrip().splitlines():
                dispatcher._print(f"  [DEBUG] run_pipeline: TRACE {_ll}")
        raise  # re-raise so existing error handling works

    # ── 盲区5: 消息流结束总结 ──
    dispatcher._print(f"  [DEBUG] run_pipeline: === MESSAGE STREAM END SUMMARY ===")
    dispatcher._print(f"  [DEBUG] run_pipeline: total messages = {dispatcher._msg_count}")
    dispatcher._print(f"  [DEBUG] run_pipeline: message type distribution = {dispatcher._msg_type_stats}")
    dispatcher._print(f"  [DEBUG] run_pipeline: assistant messages = {dispatcher._assistant_msg_count}")
    dispatcher._print(f"  [DEBUG] run_pipeline: tool_use_count = {dispatcher.tool_use_count}")
    dispatcher._print(f"  [DEBUG] run_pipeline: tool_stats = {dispatcher.tool_stats}")
    dispatcher._print(f"  [DEBUG] run_pipeline: collected_text blocks = {len(dispatcher.collected_text)}")
    if dispatcher.collected_text:
        total_chars = sum(len(t) for t in dispatcher.collected_text)
        dispatcher._print(f"  [DEBUG] run_pipeline: collected_text total chars = {total_chars}")
    dispatcher._print(f"  [DEBUG] run_pipeline: video_output (early) = {dispatcher.video_output!r}")
    dispatcher._print(f"  [DEBUG] run_pipeline: pipeline_output (early) = {'set' if dispatcher.pipeline_output is not None else 'None'}")

    # ── CLI stderr 统计 ──
    options.stderr = _saved_stderr  # 恢复原始回调
    dispatcher._print(f"  [DEBUG] run_pipeline: CLI stderr lines captured = {len(_cli_stderr_lines)}")
    if _cli_stderr_lines:
        # 只打印包含错误/警告关键词的行
        _err_keywords = ("error", "warn", "fail", "exception", "exit", "kill")
        for _sline in _cli_stderr_lines:
            _slower = _sline.lower()
            if any(kw in _slower for kw in _err_keywords):
                dispatcher._print(f"  [DEBUG] CLI STDERR: {_sline[:300]}")
        # 如果没有匹配关键词但行数很少，全部打印
        if len(_cli_stderr_lines) <= 10:
            for _sline in _cli_stderr_lines:
                dispatcher._print(f"  [DEBUG] CLI STDERR(all): {_sline[:200]}")

    # 将 dispatcher 传给调用方（用于提取 pipeline_output 等元数据）
    if _dispatcher_ref is not None:
        _dispatcher_ref.append(dispatcher)

    # 3. 从 dispatcher 提取结果
    # ── 阶段标记：SDK 对话结束，提取输出 ──
    dispatcher._print(f"  {_EMOJI['gear']} Phase 2/4: 提取渲染结果...")
    dispatcher._print(
        f"  [DEBUG] run_pipeline: dispatcher.video_output (before get_pipeline_output) = {dispatcher.video_output!r}"
    )
    dispatcher._print(
        f"  [DEBUG] run_pipeline: hook captured source code keys = {list(_hook_state.captured_source_code.keys())}"
    )
    po = dispatcher.get_pipeline_output()
    dispatcher._print(f"  [DEBUG] run_pipeline: PipelineOutput after get_pipeline_output: {po!r}")
    video_output = dispatcher.get_video_output()
    dispatcher._print(
        f"  [DEBUG] run_pipeline: video_output from get_video_output = {video_output!r}"
    )

    if not video_output:
        dispatcher._print("")
        dispatcher._print(f"{_EMOJI['cross']} Claude 未生成 VIDEO_OUTPUT 标记。")
        dispatcher._print(f"  Agent 可能未能成功渲染场景。")
        if dispatcher.result_summary:
            s = dispatcher.result_summary
            dispatcher._print(f"  Turns: {s.get('turns', '?')} | Error: {s.get('is_error', '?')}")
        # 调试：打印 Agent 的完整文本输出，帮助定位问题
        collected = "\n".join(dispatcher.collected_text)
        if collected.strip():
            dispatcher._print(f"  --- Agent 文本输出（前 2000 字符）---")
            dispatcher._print(collected[:2000])
            if len(collected) > 2000:
                dispatcher._print(f"  ... (共 {len(collected)} 字符)")
            dispatcher._print(f"  --- 输出结束 ---")
        else:
            dispatcher._print(f"  (Agent 没有产生任何文本输出)")
        raise RuntimeError(
            "Claude did not produce a VIDEO_OUTPUT marker. "
            "The agent may have failed to render the scene."
        )

    # 4-5. TTS + FFmpeg（可选）
    if no_tts:
        dispatcher._print(f"\n{_EMOJI['video']} 输出静音视频: {video_output}")
        return video_output

    # ── 阶段标记：TTS 语音合成 ──
    dispatcher._print(f"  {_EMOJI['gear']} Phase 3/4: TTS 语音合成...")

    # TTS 合成（优先使用 Claude 生成的解说词，fallback 到用户原始输入）
    po = dispatcher.get_pipeline_output()
    narration_text = po.narration if po and po.narration else user_text
    dispatcher._print(f"\n{_EMOJI['tts']} TTS 合成中... (voice={voice_id}, model={model})")
    tts_result = await tts_client.synthesize(
        text=narration_text,
        voice_id=voice_id,
        model=model,
        output_dir=str(Path(output_path).parent),
    )
    dispatcher._print(f"  TTS 完成: {tts_result.duration_ms}ms, {tts_result.word_count} chars")

    # FFmpeg 合成
    # ── 阶段标记：最终合成 ──
    dispatcher._print(f"[MUX] Phase 4/4: FFmpeg 视频合成...")
    dispatcher._print(f"[MUX] FFmpeg 合成中... (video + audio + subtitle)")
    final_video = await video_builder.build_final_video(
        video_path=video_output,
        audio_path=tts_result.audio_path,
        subtitle_path=tts_result.subtitle_path,
        output_path=output_path,
    )

    dispatcher._print(f"\n{_EMOJI['check']} 视频生成完成: {final_video}")
    return final_video


# ── 入口点 ────────────────────────────────────────────────────


async def main() -> None:
    """异步主入口函数。"""
    args = parse_args()

    try:
        _ = await run_pipeline(
            user_text=args.text,
            output_path=args.output,
            voice_id=args.voice,
            model=args.model,
            quality=args.quality,
            no_tts=args.no_tts,
            cwd=args.cwd,
            prompt_file=args.prompt_file,
            max_turns=args.max_turns,
        )
    except KeyboardInterrupt:
        print(f"\n{_EMOJI['cross']} 用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"\n{_EMOJI['cross']} 错误: {e}", file=sys.stderr)
        logger.exception("Pipeline failed with exception:")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
