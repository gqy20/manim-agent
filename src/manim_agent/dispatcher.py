"""消息分发器：消费 Claude Agent SDK 消息流，提取结构化信息并输出实时日志。"""

import json
import logging
from pathlib import Path
from typing import Any, Callable

from claude_agent_sdk import (
    AssistantMessage,
    Message,
    RateLimitEvent,
    ResultMessage,
    StreamEvent,
    TaskNotificationMessage,
    TaskProgressMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
)

from .hooks import _hook_state
from .output_schema import PipelineOutput
from .pipeline_events import (
    EventType,
    PipelineEvent,
    ThinkingPayload,
    ProgressPayload,
    ToolResultPayload,
    ToolStartPayload,
)

logger = logging.getLogger(__name__)

# ── 日志样式常量（ASCII-only，兼容 Windows 终端） ──────────────

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
        output_cwd: str | None = None,
    ) -> None:
        self.verbose = verbose
        self.log_callback = log_callback
        self.output_cwd = Path(output_cwd).resolve() if output_cwd else None
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

    @property
    def captured_source_code(self) -> dict[str, str]:
        """委托到 hook 状态的源码字典（向后兼容）。"""
        return _hook_state.captured_source_code

    # ── 公共接口 ──────────────────────────────────────────────

    def dispatch(self, message: Message) -> None:
        """根据消息类型路由到对应处理器。"""
        self._msg_count += 1
        msg_type = type(message).__name__
        self._msg_type_stats[msg_type] = self._msg_type_stats.get(msg_type, 0) + 1
        logger.debug("dispatch #%s: %s", self._msg_count, msg_type)

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
            logger.debug("dispatch: unhandled message type: %s, attrs=%s", msg_type, dir(message))

    def get_pipeline_output(self) -> PipelineOutput | None:
        """返回验证后的 PipelineOutput（可能为 None）。

        优先级：structured_output > Hook 捕获源码 > None
        """
        if self.pipeline_output is not None:
            logger.debug(
                "get_pipeline_output: returning cached PipelineOutput, video_output=%r",
                self.pipeline_output.video_output,
            )
            return self.pipeline_output
        # fallback：从 collected_text 的标记中解析
        logger.debug(
            "get_pipeline_output: trying text markers fallback, collected_text length=%d",
            len(self.collected_text),
        )
        try:
            self.pipeline_output = PipelineOutput.from_text_markers("\n".join(self.collected_text))
            logger.debug(
                "get_pipeline_output: text markers parsed, video_output=%r",
                self.pipeline_output.video_output,
            )
        except (ValueError, Exception) as e:
            logger.debug("get_pipeline_output: text markers failed: %s", e)
            discovered_video = self._discover_rendered_video_path()
            if not discovered_video:
                return None
            self.pipeline_output = PipelineOutput(
                video_output=discovered_video,
                scene_file=self._infer_scene_file(),
            )
            logger.debug(
                "get_pipeline_output: built fallback PipelineOutput from runtime artifacts, "
                "video_output=%r",
                discovered_video,
            )
        self._attach_captured_source_code("get_pipeline_output")
        # 同步向后兼容属性
        self._sync_compat_attrs()
        return self.pipeline_output

    def get_video_output(self) -> str | None:
        """返回提取到的视频输出路径（向后兼容接口）。"""
        if self.pipeline_output is not None and self.pipeline_output.video_output:
            return self.pipeline_output.video_output
        if self.video_output:
            return self.video_output
        po = self.get_pipeline_output()
        return po.video_output if po else None

    # ── 消息处理器 ──────────────────────────────────────────────

    def _handle_assistant(self, msg: AssistantMessage) -> None:
        """处理 AssistantMessage，遍历所有 content block。

        注意：源码捕获已移至 SDK Hook 系统（PostToolUseHookInput）。
        """
        self._assistant_msg_count += 1
        logger.debug(
            "_handle_assistant #%d: stop_reason=%r, model=%r, error=%r, blocks=%d, message_id=%r",
            self._assistant_msg_count, msg.stop_reason, msg.model,
            msg.error, len(msg.content), msg.message_id,
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
                    logger.debug("_handle_assistant: %s tool called (hook will capture source)", name)

            elif isinstance(block, ToolResultBlock):
                self._log_tool_result(block)

            elif isinstance(block, ThinkingBlock):
                self._log_thinking(block)

    def _handle_result(self, msg: ResultMessage) -> None:
        """处理 ResultMessage，记录会话摘要并尝试解析 structured_output。"""
        self._result_message = msg
        logger.debug(
            "_handle_result: stop_reason=%r, is_error=%s, num_turns=%d",
            msg.stop_reason, msg.is_error, msg.num_turns,
        )
        logger.debug(
            "_handle_result: duration_ms=%d, duration_api_ms=%d",
            msg.duration_ms, msg.duration_api_ms,
        )
        logger.debug("_handle_result: session_id=%r, uuid=%r", msg.session_id, msg.uuid)
        if msg.total_cost_usd is not None:
            logger.debug("_handle_result: total_cost_usd=%s", msg.total_cost_usd)
        if msg.usage:
            logger.debug("_handle_result: usage=%s", msg.usage)
        if msg.model_usage:
            logger.debug("_handle_result: model_usage=%s", msg.model_usage)
        if msg.errors:
            logger.debug("_handle_result: ERRORS=%s", msg.errors)
        if msg.permission_denials:
            logger.debug("_handle_result: PERMISSION_DENIALS=%s", msg.permission_denials)
        if msg.result:
            logger.debug("_handle_result: result (preview)=%r", str(msg.result)[:300])
        logger.debug(
            "_handle_result: structured_output is %s",
            "not None" if msg.structured_output is not None else "None",
        )
        if msg.structured_output is not None:
            logger.debug(
                "_handle_result: structured_output type=%s, value=%r",
                type(msg.structured_output).__name__,
                str(msg.structured_output)[:500],
            )
        # ── 尝试从 structured_output 构建 PipelineOutput（主路径）──
        if msg.structured_output is not None:
            try:
                raw = msg.structured_output
                logger.debug("_handle_result: raw type=%s", type(raw).__name__)
                if isinstance(raw, str):
                    raw = json.loads(raw)
                    logger.debug("_handle_result: parsed JSON, type=%s", type(raw).__name__)
                if not isinstance(raw, dict):
                    raise ValueError(f"structured_output unexpected type: {type(raw).__name__}")
                self.pipeline_output = PipelineOutput.model_validate(raw)
                logger.debug(
                    "_handle_result: PipelineOutput validated, video_output=%r",
                    self.pipeline_output.video_output,
                )
                # 关联 Hook 捕获的源代码
                if (
                    self.pipeline_output.scene_file
                    and self.pipeline_output.scene_file in _hook_state.captured_source_code
                ):
                    self.pipeline_output.source_code = _hook_state.captured_source_code[
                        self.pipeline_output.scene_file
                    ]
                    logger.debug(
                        "_handle_result: source code linked for %s",
                        self.pipeline_output.scene_file,
                    )
                else:
                    self._attach_captured_source_code("_handle_result")
                self._sync_compat_attrs()
            except Exception as e:
                logger.warning(
                    "structured_output validation failed, falling back to text markers: %s", e
                )
                logger.debug("_handle_result: validation failed: %s", e)
        else:
            logger.debug("_handle_result: no structured_output, will try text markers fallback")
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
        logger.debug(
            "_handle_task_notification: output_file=%r, status=%s",
            msg.output_file, msg.status,
        )
        if msg.status == "completed" and msg.output_file:
            self.video_output = msg.output_file
            self._print(
                f"  {_EMOJI['video']} Video output from task_notification: {msg.output_file}"
            )
        elif msg.status == "completed" and not msg.output_file:
            logger.debug("_handle_task_notification: completed but no output_file")

    def _handle_stream_event(self, msg: StreamEvent) -> None:
        """处理流式事件（token 级别的 API 增量更新）。"""
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

    def _discover_rendered_video_path(self) -> str | None:
        """Discover a rendered MP4 from SDK signals or task output artifacts."""
        if self.video_output:
            return self.video_output
        if not self.output_cwd:
            return None

        candidate_dirs = [self.output_cwd / "media" / "videos"]
        seen: set[Path] = set()
        candidates: list[Path] = []
        for base_dir in candidate_dirs:
            if not base_dir.exists():
                continue
            for path in base_dir.rglob("*.mp4"):
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                candidates.append(resolved)

        if not candidates:
            logger.debug(
                "_discover_rendered_video_path: no mp4 found under %s", self.output_cwd
            )
            return None

        best = max(candidates, key=lambda p: p.stat().st_mtime)
        best_str = str(best)
        logger.debug(
            "_discover_rendered_video_path: selected %r from %d candidate(s)",
            best_str, len(candidates),
        )
        return best_str

    def _infer_scene_file(self) -> str | None:
        """Infer the scene file from hook-captured Python files under the task cwd."""
        if self.scene_file:
            return self.scene_file
        captured_paths = [Path(p).resolve() for p in _hook_state.captured_source_code]
        if self.output_cwd is not None:
            captured_paths = [
                p for p in captured_paths
                if self.output_cwd in p.parents
            ]
        if len(captured_paths) == 1:
            return str(captured_paths[0])
        return None

    def _attach_captured_source_code(self, context: str) -> None:
        """Link hook-captured source into PipelineOutput when possible."""
        if self.pipeline_output is None:
            return

        scene_file = self.pipeline_output.scene_file or self._infer_scene_file()
        if scene_file:
            self.pipeline_output.scene_file = scene_file

        if (
            self.pipeline_output.scene_file
            and self.pipeline_output.scene_file in _hook_state.captured_source_code
        ):
            self.pipeline_output.source_code = _hook_state.captured_source_code[
                self.pipeline_output.scene_file
            ]
            logger.debug("%s: source code linked from hook state", context)
        else:
            logger.debug(
                "%s: scene_file=%r, hook captured keys=%s",
                context,
                self.pipeline_output.scene_file,
                list(_hook_state.captured_source_code.keys()),
            )

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
        logger.debug("_log_tool_use: id=%s, name=%s", block.id, block.name)
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
        """打印工具执行结果 + 发射 TOOL_RESULT 结构化事件。"""
        content = block.content
        if content:
            if isinstance(content, str):
                full_content = content.replace("\n", "\\n")
                if len(full_content) > 500:
                    logger.debug(
                        "_log_tool_result: tool_use_id=%s, is_error=%s, content_length=%d",
                        block.tool_use_id, block.is_error, len(content),
                    )
                    logger.debug(
                        "_log_tool_result: FULL CONTENT (first 1000):\n%s",
                        full_content[:1000],
                    )
                    if len(full_content) > 1000:
                        logger.debug(
                            "_log_tool_result: ... (truncated, total %d chars)", len(content)
                        )
                else:
                    logger.debug(
                        "_log_tool_result: tool_use_id=%s, is_error=%s, content=%r",
                        block.tool_use_id, block.is_error, full_content,
                    )
            elif isinstance(content, list):
                logger.debug(
                    "_log_tool_result: tool_use_id=%s, is_error=%s, content_parts=%d",
                    block.tool_use_id, block.is_error, len(content),
                )
                for i, part in enumerate(content):
                    part_str = str(part)
                    preview = part_str[:300].replace("\n", "\\n")
                    logger.debug(
                        "_log_tool_result:   part[%d] type=%s, preview=%r",
                        i, type(part).__name__, preview,
                    )
                    if len(part_str) > 300:
                        logger.debug(
                            "_log_tool_result:   part[%d] ... (total %d chars)",
                            i, len(part_str),
                        )
        else:
            logger.debug(
                "_log_tool_result: tool_use_id=%s, is_error=%s, content=None/empty",
                block.tool_use_id, block.is_error,
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
