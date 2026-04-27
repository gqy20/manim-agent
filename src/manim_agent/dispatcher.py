"""消息分发器：消费 Claude Agent SDK 消息流，提取结构化信息并输出实时日志。"""

import json
import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

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

from .hooks import _HookState, get_hook_state, normalize_path_string
from .pipeline_events import (
    EventType,
    PipelineEvent,
    ProgressPayload,
    ThinkingPayload,
    ToolResultPayload,
    ToolStartPayload,
)
from .schemas import (
    Phase1PlanningOutput,
    Phase2ImplementationOutput,
    Phase2ScriptDraftOutput,
    PipelineOutput,
)
from .segment_renderer import discover_segment_video_paths
from .token_pricing import estimate_result_cost_cny, estimate_token_cost_cny

logger = logging.getLogger(__name__)


def _to_jsonable(value: Any) -> Any:
    """Best-effort conversion for diagnostic dumps."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v) for v in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _to_jsonable(model_dump())
    return str(value)

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
        hook_state: _HookState | None = None,
        expected_output: Literal[
            "pipeline_output",
            "phase1_planning",
            "phase2_script_draft",
            "phase2_implementation",
        ] = "pipeline_output",
    ) -> None:
        self.verbose = verbose
        self.log_callback = log_callback
        self.output_cwd = Path(output_cwd).resolve() if output_cwd else None
        self._hook_state = hook_state or get_hook_state()
        self.expected_output = expected_output
        self.event_callback: Callable[[PipelineEvent], None] | None = None
        self.turn_count = 0
        self.tool_use_count = 0
        self.tool_stats: dict[str, int] = {}
        self.collected_text: list[str] = []
        self.implementation_started: bool = False
        # ── 工具配对表：tool_use_id → (name, start_time_ms) ──
        self._pending_tools: dict[str, tuple[str, int]] = {}
        # ── PostToolUseFailure 错误记录 ──
        self._tool_failures: dict[str, tuple[str, str]] = {}  # id → (error_type, message)
        self.implementation_start_reason: str | None = None
        # ── 消息统计（调试用）──
        self._msg_count: int = 0
        self._msg_type_stats: dict[str, int] = {}
        self._assistant_msg_count: int = 0
        self.last_model_name: str | None = None
        # ── PipelineOutput ──
        self.pipeline_output: PipelineOutput | None = None
        self.scene_plan_output: Phase1PlanningOutput | None = None
        self.phase2_script_draft_output: Phase2ScriptDraftOutput | None = None
        self.phase2_implementation_output: Phase2ImplementationOutput | None = None
        self._structured_output_candidate: PipelineOutput | None = None
        self._result_output_candidate: PipelineOutput | None = None
        self._scene_plan_output_candidate: Phase1PlanningOutput | None = None
        self._phase2_script_draft_output_candidate: Phase2ScriptDraftOutput | None = None
        self._phase2_implementation_output_candidate: Phase2ImplementationOutput | None = None
        self.raw_result_text: str | None = None
        self.raw_structured_output: Any = None
        self.scene_plan_validation_error: str | None = None
        self._saw_completed_task_notification = False
        self.task_notification_status: str | None = None
        self.task_notification_summary: str | None = None
        self.task_notification_output_file: str | None = None
        # ── 视频输出路径（从 TaskNotificationMessage.output_file 获取）──
        self.video_output: str | None = None
        # ── 向后兼容的旧属性 ──
        self.scene_file: str | None = None
        self.scene_class: str | None = None
        self._bash_commands: list[str] = []
        # ── 直接使用 ResultMessage 原生字段，不再手动构建 ──

    @property
    def captured_source_code(self) -> dict[str, str]:
        """委托到 hook 状态的源码字典（向后兼容）。"""
        return self._hook_state.captured_source_code

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
        """返回验证后的 PipelineOutput（可能为 None）。"""
        if self.pipeline_output is not None:
            if self._structured_output_candidate is not None:
                self._merge_pipeline_output(self._structured_output_candidate)
            if self._result_output_candidate is not None:
                self._merge_pipeline_output(self._result_output_candidate)
            self._attach_captured_source_code("get_pipeline_output[cached]")
            if not self.pipeline_output.scene_class:
                self.pipeline_output.scene_class = self._infer_scene_class()
            self._sync_compat_attrs()
            logger.debug(
                "get_pipeline_output: returning cached PipelineOutput, video_output=%r",
                self.pipeline_output.video_output,
            )
            return self.pipeline_output
        if self._result_output_candidate is not None:
            self.pipeline_output = self._result_output_candidate
            logger.debug(
                "get_pipeline_output: using ResultMessage fallback, video_output=%r",
                self.pipeline_output.video_output,
            )
            self._attach_captured_source_code("get_pipeline_output[result]")
            self._sync_compat_attrs()
            return self.pipeline_output
        if not self._saw_completed_task_notification and not hasattr(self, "_result_message"):
            logger.debug(
                "get_pipeline_output: neither completed task notification nor "
                "ResultMessage observed; "
                "text/structured fallback only",
            )
        # fallback：文件系统扫描已渲染的 mp4
        discovered_video = self._discover_rendered_video_path()
        if discovered_video:
            self.pipeline_output = PipelineOutput(
                video_output=discovered_video,
                scene_file=self._infer_scene_file(),
                scene_class=self._infer_scene_class(),
            )
            logger.debug(
                "get_pipeline_output: built PipelineOutput from filesystem scan, video_output=%r",
                discovered_video,
            )
        else:
            discovered_segments = self._discover_rendered_segment_paths()
            if not discovered_segments:
                logger.debug("get_pipeline_output: unable to discover rendered video or segments")
                return None
            self.pipeline_output = PipelineOutput(
                video_output=None,
                scene_file=self._infer_scene_file(),
                scene_class=self._infer_scene_class(),
                render_mode="segments",
                segment_render_complete=True,
                segment_video_paths=discovered_segments,
            )
            logger.debug(
                "get_pipeline_output: built segment-first PipelineOutput from filesystem scan, "
                "segments=%r",
                discovered_segments,
            )
        self._attach_captured_source_code("get_pipeline_output")
        self._sync_compat_attrs()
        return self.pipeline_output

    def get_scene_plan_output(self) -> Phase1PlanningOutput | None:
        """Return the best-known structured planning output, if any."""
        if self.scene_plan_output is not None:
            return self.scene_plan_output
        if self._scene_plan_output_candidate is not None:
            self.scene_plan_output = self._scene_plan_output_candidate
            return self.scene_plan_output
        return None

    def get_phase2_implementation_output(self) -> Phase2ImplementationOutput | None:
        """Return the best-known structured implementation output, if any."""
        if self.phase2_implementation_output is not None:
            return self.phase2_implementation_output
        if self._phase2_implementation_output_candidate is not None:
            self.phase2_implementation_output = self._phase2_implementation_output_candidate
            return self.phase2_implementation_output
        return None

    def get_phase2_script_draft_output(self) -> Phase2ScriptDraftOutput | None:
        """Return the best-known structured script draft output, if any."""
        if self.phase2_script_draft_output is not None:
            return self.phase2_script_draft_output
        if self._phase2_script_draft_output_candidate is not None:
            self.phase2_script_draft_output = self._phase2_script_draft_output_candidate
            return self.phase2_script_draft_output
        return None

    def get_phase1_failure_diagnostics(self) -> dict[str, Any]:
        """Return raw planning artifacts useful when Phase 1 validation fails."""
        return {
            "raw_structured_output_present": self.raw_structured_output is not None,
            "raw_structured_output_type": (
                type(self.raw_structured_output).__name__
                if self.raw_structured_output is not None
                else None
            ),
            "scene_plan_validation_error": self.scene_plan_validation_error,
            "raw_structured_output": _to_jsonable(self.raw_structured_output),
            "raw_result_text": self.raw_result_text,
            "collected_text": "\n".join(self.collected_text).strip() or None,
            "partial_plan_text": getattr(self, "partial_plan_text", None),
            "result_summary": self.result_summary,
            "tool_use_count": self.tool_use_count,
            "tool_stats": dict(self.tool_stats),
        }

    def get_video_output(self) -> str | None:
        """返回视频输出路径，纯便捷包装（委托给 get_pipeline_output）。"""
        po = self.get_pipeline_output()
        return po.video_output if po else None

    def get_persistable_pipeline_output(self) -> dict[str, Any] | None:
        """Return the best-known structured output, even for partial or failed runs."""
        po = self.get_pipeline_output()
        if po is not None:
            payload = po.model_dump()
            if payload.get("phase1_planning") is None:
                scene_plan_output = getattr(self, "scene_plan_output", None)
                if scene_plan_output is not None:
                    payload["phase1_planning"] = scene_plan_output.model_dump()
            return payload

        discovered_video = self._discover_rendered_video_path()
        discovered_segments = self._discover_rendered_segment_paths()
        payload: dict[str, Any] = {
            "video_output": discovered_video,
            "final_video_output": None,
            "scene_file": self._infer_scene_file(),
            "scene_class": self._infer_scene_class(),
            "duration_seconds": None,
            "narration": None,
            "implemented_beats": [],
            "build_summary": getattr(self, "partial_build_summary", None),
            "deviations_from_plan": list(getattr(self, "partial_deviations_from_plan", [])),
            "beat_to_narration_map": list(getattr(self, "partial_beat_to_narration_map", [])),
            "narration_coverage_complete": getattr(
                self, "partial_narration_coverage_complete", None
            ),
            "estimated_narration_duration_seconds": getattr(
                self,
                "partial_estimated_narration_duration_seconds",
                None,
            ),
            "render_mode": getattr(self, "partial_render_mode", None)
            or ("segments" if discovered_segments and not discovered_video else None),
            "segment_render_complete": getattr(self, "partial_segment_render_complete", None)
            if getattr(self, "partial_segment_render_complete", None) is not None
            else (True if discovered_segments and not discovered_video else None),
            "beats": [],
            "audio_segments": [],
            "timeline_path": None,
            "timeline_total_duration_seconds": None,
            "segment_render_plan_path": None,
            "segment_video_paths": discovered_segments,
            "audio_concat_path": None,
            "source_code": None,
            "audio_path": None,
            "bgm_path": None,
            "bgm_prompt": None,
            "bgm_duration_ms": None,
            "bgm_volume": None,
            "audio_mix_mode": None,
            "subtitle_path": None,
            "extra_info_path": None,
            "tts_mode": None,
            "tts_duration_ms": None,
            "tts_word_count": None,
            "tts_usage_characters": None,
            "run_turns": getattr(self, "partial_run_turns", None),
            "run_tool_use_count": getattr(self, "partial_run_tool_use_count", None),
            "run_tool_stats": dict(getattr(self, "partial_run_tool_stats", {})),
            "run_duration_ms": getattr(self, "partial_run_duration_ms", None),
            "run_cost_usd": getattr(self, "partial_run_cost_usd", None),
            "run_cost_cny": getattr(self, "partial_run_cost_cny", None),
            "run_model_name": getattr(self, "partial_run_model_name", None),
            "run_pricing_model": getattr(self, "partial_run_pricing_model", None),
            "target_duration_seconds": getattr(self, "partial_target_duration_seconds", None),
            "plan_text": getattr(self, "partial_plan_text", None),
            "review_summary": getattr(self, "partial_review_summary", None),
            "review_approved": getattr(self, "partial_review_approved", None),
            "review_blocking_issues": list(getattr(self, "partial_review_blocking_issues", [])),
            "review_suggested_edits": list(getattr(self, "partial_review_suggested_edits", [])),
            "review_frame_paths": list(getattr(self, "partial_review_frame_paths", [])),
            "phase1_planning": None,
        }

        scene_file = payload["scene_file"]
        if scene_file and scene_file in self._hook_state.captured_source_code:
            payload["source_code"] = self._hook_state.captured_source_code[scene_file]

        scene_plan_output = getattr(self, "scene_plan_output", None)
        if payload["phase1_planning"] is None and scene_plan_output is not None:
            payload["phase1_planning"] = scene_plan_output.model_dump()

        if any(value not in (None, "", [], {}) for value in payload.values()):
            return payload
        return None

    # ── 消息处理器 ──────────────────────────────────────────────

    def _handle_assistant(self, msg: AssistantMessage) -> None:
        """处理 AssistantMessage，遍历所有 content block。

        注意：源码捕获已移至 SDK Hook 系统（PostToolUseHookInput）。
        """
        self._assistant_msg_count += 1
        logger.debug(
            "_handle_assistant #%d: stop_reason=%r, model=%r, error=%r, blocks=%d, message_id=%r",
            self._assistant_msg_count,
            msg.stop_reason,
            msg.model,
            msg.error,
            len(msg.content),
            msg.message_id,
        )
        if msg.model:
            self.last_model_name = msg.model
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
                    logger.debug(
                        "_handle_assistant: %s tool called (hook will capture source)", name
                    )

            elif isinstance(block, ToolResultBlock):
                self._log_tool_result(block)

            elif isinstance(block, ThinkingBlock):
                self._log_thinking(block)

    def _handle_result(self, msg: ResultMessage) -> None:
        """处理 ResultMessage，记录会话摘要并尝试解析 structured_output。"""
        self._result_message = msg
        self.raw_result_text = msg.result if isinstance(msg.result, str) else None
        self.raw_structured_output = msg.structured_output
        logger.debug(
            "_handle_result: stop_reason=%r, is_error=%s, num_turns=%d",
            msg.stop_reason,
            msg.is_error,
            msg.num_turns,
        )
        logger.debug(
            "_handle_result: duration_ms=%d, duration_api_ms=%d",
            msg.duration_ms,
            msg.duration_api_ms,
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
        # ── 从 structured_output 构建 PipelineOutput（主路径）──
        if msg.structured_output is not None and self.expected_output == "pipeline_output":
            try:
                validated_output = self._build_pipeline_output_from_raw(
                    msg.structured_output,
                    source="structured_output",
                )
                self._structured_output_candidate = validated_output
                logger.debug(
                    "_handle_result: PipelineOutput validated, video_output=%r",
                    validated_output.video_output,
                )
                # 关联 Hook 捕获的源代码
                if (
                    validated_output.scene_file
                    and validated_output.scene_file in self._hook_state.captured_source_code
                ):
                    validated_output.source_code = self._hook_state.captured_source_code[
                        validated_output.scene_file
                    ]
                    logger.debug(
                        "_handle_result: source code linked for %s",
                        validated_output.scene_file,
                    )
                self._attach_captured_source_code("_handle_result")
                if self.pipeline_output is None:
                    self.pipeline_output = validated_output
                else:
                    self._merge_pipeline_output(validated_output)
                self._sync_compat_attrs()
            except Exception as e:
                logger.warning("structured_output validation failed: %s", e)
                logger.debug("_handle_result: validation failed: %s", e)
        if msg.structured_output is not None and self.expected_output == "phase1_planning":
            try:
                scene_plan_output = self._build_scene_plan_output_from_raw(
                    msg.structured_output,
                    source="structured_output",
                )
                self._scene_plan_output_candidate = scene_plan_output
                if self.scene_plan_output is None:
                    self.scene_plan_output = scene_plan_output
                logger.debug(
                    "_handle_result: Phase1PlanningOutput validated with %d beat(s)",
                    len(scene_plan_output.build_spec.beats),
                )
            except Exception as e:
                self.scene_plan_validation_error = str(e)
                logger.debug("_handle_result: scene plan validation failed: %s", e)
        if msg.structured_output is not None and self.expected_output == "phase2_script_draft":
            try:
                draft_output = self._build_phase2_script_draft_output_from_raw(
                    msg.structured_output,
                    source="structured_output",
                )
                self._phase2_script_draft_output_candidate = draft_output
                if self.phase2_script_draft_output is None:
                    self.phase2_script_draft_output = draft_output
                logger.debug(
                    "_handle_result: Phase2ScriptDraftOutput validated with %d beat(s)",
                    len(draft_output.implemented_beats),
                )
            except Exception as e:
                logger.debug("_handle_result: phase2 script draft validation failed: %s", e)
        if msg.structured_output is not None and self.expected_output == "phase2_implementation":
            try:
                phase2_output = self._build_phase2_implementation_output_from_raw(
                    msg.structured_output,
                    source="structured_output",
                )
                self._phase2_implementation_output_candidate = phase2_output
                if self.phase2_implementation_output is None:
                    self.phase2_implementation_output = phase2_output
                logger.debug(
                    "_handle_result: Phase2ImplementationOutput validated with %d beat(s)",
                    len(phase2_output.implemented_beats),
                )
            except Exception as e:
                logger.debug("_handle_result: phase2 implementation validation failed: %s", e)
        elif msg.structured_output is None:
            logger.debug("_handle_result: no structured_output")
        if self.expected_output == "pipeline_output" and msg.result:
            try:
                result_candidate = self._build_pipeline_output_from_result_text(msg.result)
                if result_candidate is not None:
                    self._result_output_candidate = result_candidate
                    logger.debug(
                        "_handle_result: ResultMessage.result produced fallback video_output=%r",
                        result_candidate.video_output,
                    )
            except Exception as e:
                logger.warning("result fallback parsing failed: %s", e)
                logger.debug("_handle_result: result fallback validation failed: %s", e)
        if (
            self.expected_output == "pipeline_output"
            and self._result_output_candidate is None
            and self.collected_text
        ):
            try:
                text_candidate = self._extract_pipeline_output_from_embedded_json(
                    "\n".join(self.collected_text),
                    source="assistant_text_embedded_json",
                )
                if text_candidate is not None:
                    self._result_output_candidate = text_candidate
                    logger.debug(
                        "_handle_result: assistant text produced fallback video_output=%r",
                        text_candidate.video_output,
                    )
            except Exception as e:
                logger.warning("assistant-text fallback parsing failed: %s", e)
                logger.debug("_handle_result: assistant-text validation failed: %s", e)
        self._log_result_summary()

    @property
    def result_summary(self) -> dict[str, Any] | None:
        """返回 ResultMessage 字段的字典视图（向后兼容）。"""
        if not hasattr(self, "_result_message") or self._result_message is None:
            return None
        msg = self._result_message
        cost_estimate = estimate_result_cost_cny(
            self.last_model_name,
            msg.usage,
            msg.model_usage,
        )
        return {
            "turns": msg.num_turns,
            "cost_usd": msg.total_cost_usd,
            "cost_cny": cost_estimate.get("estimated_cost_cny"),
            "pricing_model": cost_estimate.get("pricing_model"),
            "input_tokens": cost_estimate.get("input_tokens"),
            "output_tokens": cost_estimate.get("output_tokens"),
            "cache_read_tokens": cost_estimate.get("cache_read_tokens"),
            "cache_write_tokens": cost_estimate.get("cache_write_tokens"),
            "total_tokens": cost_estimate.get("total_tokens"),
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
        cost_estimate = estimate_token_cost_cny(self.last_model_name, usage)
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
                    model_name=cost_estimate.get("model_name"),
                    pricing_model=cost_estimate.get("pricing_model"),
                    input_tokens=cost_estimate.get("input_tokens"),
                    output_tokens=cost_estimate.get("output_tokens"),
                    cache_read_tokens=cost_estimate.get("cache_read_tokens"),
                    cache_write_tokens=cost_estimate.get("cache_write_tokens"),
                    estimated_cost_cny=cost_estimate.get("estimated_cost_cny"),
                    cost_estimate_note=cost_estimate.get("cost_estimate_note"),
                    last_tool_name=None,
                ),
            )
        )

    def _handle_task_notification(self, msg: TaskNotificationMessage) -> None:
        """处理任务完成/失败通知。

        使用 SDK 原生的 TaskNotificationMessage.output_file 获取视频路径，
        无需解析文本标记。
        """
        if msg.status == "completed":
            icon = _EMOJI["check"]
            self._print(f"  {icon} Task completed: {msg.summary}")
        elif msg.status == "stopped":
            icon = _EMOJI["cross"]
            self._print(f"  {icon} Task stopped: {msg.summary}")
        else:
            icon = _EMOJI["cross"]
            self._print(f"  {icon} Task failed: {msg.summary}")
        logger.debug(
            "_handle_task_notification: output_file=%r, status=%s",
            msg.output_file,
            msg.status,
        )
        self.task_notification_status = msg.status
        self.task_notification_summary = msg.summary
        self.task_notification_output_file = (
            normalize_path_string(msg.output_file) if msg.output_file else None
        )
        if msg.status == "completed":
            self._saw_completed_task_notification = True
        if msg.status == "completed" and msg.output_file:
            normalized_output = normalize_path_string(msg.output_file)
            if self._looks_like_rendered_video(normalized_output):
                self.video_output = normalized_output
                self.pipeline_output = PipelineOutput(
                    video_output=normalized_output,
                    scene_file=self._infer_scene_file(),
                    scene_class=self._infer_scene_class(),
                )
                self._sync_compat_attrs()
                self._print(
                    f"  {_EMOJI['video']} Video output from task_notification: {normalized_output}"
                )
            else:
                logger.debug(
                    "_handle_task_notification: ignoring non-video output_file=%r",
                    normalized_output,
                )
                self._print(
                    "  [WARN] Task notification provided a non-video output artifact; "
                    "falling back to structured output or filesystem scan."
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

    def _merge_pipeline_output(self, incoming: PipelineOutput) -> None:
        """Merge richer structured fields into an existing pipeline output."""
        if self.pipeline_output is None:
            self.pipeline_output = incoming
            return

        current = self.pipeline_output
        current.video_output = incoming.video_output or current.video_output
        current.final_video_output = incoming.final_video_output or current.final_video_output
        current.scene_file = incoming.scene_file or current.scene_file
        current.scene_class = incoming.scene_class or current.scene_class
        current.duration_seconds = (
            incoming.duration_seconds
            if incoming.duration_seconds is not None
            else current.duration_seconds
        )
        current.narration = incoming.narration or current.narration
        if incoming.implemented_beats:
            current.implemented_beats = incoming.implemented_beats
        current.build_summary = incoming.build_summary or current.build_summary
        if incoming.deviations_from_plan:
            current.deviations_from_plan = incoming.deviations_from_plan
        if incoming.beat_to_narration_map:
            current.beat_to_narration_map = incoming.beat_to_narration_map
        current.narration_coverage_complete = (
            incoming.narration_coverage_complete
            if incoming.narration_coverage_complete is not None
            else current.narration_coverage_complete
        )
        current.estimated_narration_duration_seconds = (
            incoming.estimated_narration_duration_seconds
            if incoming.estimated_narration_duration_seconds is not None
            else current.estimated_narration_duration_seconds
        )
        current.render_mode = incoming.render_mode or current.render_mode
        current.segment_render_complete = (
            incoming.segment_render_complete
            if incoming.segment_render_complete is not None
            else current.segment_render_complete
        )
        if incoming.beats:
            current.beats = incoming.beats
        if incoming.audio_segments:
            current.audio_segments = incoming.audio_segments
        current.timeline_path = incoming.timeline_path or current.timeline_path
        current.timeline_total_duration_seconds = (
            incoming.timeline_total_duration_seconds
            if incoming.timeline_total_duration_seconds is not None
            else current.timeline_total_duration_seconds
        )
        current.segment_render_plan_path = (
            incoming.segment_render_plan_path or current.segment_render_plan_path
        )
        if incoming.segment_video_paths:
            current.segment_video_paths = incoming.segment_video_paths
        current.audio_concat_path = incoming.audio_concat_path or current.audio_concat_path
        current.source_code = incoming.source_code or current.source_code
        current.audio_path = incoming.audio_path or current.audio_path
        current.bgm_path = incoming.bgm_path or current.bgm_path
        current.bgm_prompt = incoming.bgm_prompt or current.bgm_prompt
        current.bgm_duration_ms = (
            incoming.bgm_duration_ms
            if incoming.bgm_duration_ms is not None
            else current.bgm_duration_ms
        )
        current.bgm_volume = (
            incoming.bgm_volume if incoming.bgm_volume is not None else current.bgm_volume
        )
        current.audio_mix_mode = incoming.audio_mix_mode or current.audio_mix_mode
        current.subtitle_path = incoming.subtitle_path or current.subtitle_path
        current.extra_info_path = incoming.extra_info_path or current.extra_info_path
        current.tts_mode = incoming.tts_mode or current.tts_mode
        current.tts_duration_ms = (
            incoming.tts_duration_ms
            if incoming.tts_duration_ms is not None
            else current.tts_duration_ms
        )
        current.tts_word_count = (
            incoming.tts_word_count
            if incoming.tts_word_count is not None
            else current.tts_word_count
        )
        current.tts_usage_characters = (
            incoming.tts_usage_characters
            if incoming.tts_usage_characters is not None
            else current.tts_usage_characters
        )
        current.run_turns = (
            incoming.run_turns if incoming.run_turns is not None else current.run_turns
        )
        current.run_tool_use_count = (
            incoming.run_tool_use_count
            if incoming.run_tool_use_count is not None
            else current.run_tool_use_count
        )
        if incoming.run_tool_stats:
            current.run_tool_stats = incoming.run_tool_stats
        current.run_duration_ms = (
            incoming.run_duration_ms
            if incoming.run_duration_ms is not None
            else current.run_duration_ms
        )
        current.run_cost_usd = (
            incoming.run_cost_usd if incoming.run_cost_usd is not None else current.run_cost_usd
        )
        current.run_cost_cny = (
            incoming.run_cost_cny if incoming.run_cost_cny is not None else current.run_cost_cny
        )
        current.run_model_name = incoming.run_model_name or current.run_model_name
        current.run_pricing_model = incoming.run_pricing_model or current.run_pricing_model
        current.target_duration_seconds = (
            incoming.target_duration_seconds
            if incoming.target_duration_seconds is not None
            else current.target_duration_seconds
        )
        current.plan_text = incoming.plan_text or current.plan_text
        current.review_summary = incoming.review_summary or current.review_summary
        if incoming.phase1_planning is not None and current.phase1_planning is None:
            current.phase1_planning = incoming.phase1_planning
        current.review_approved = (
            incoming.review_approved
            if incoming.review_approved is not None
            else current.review_approved
        )
        if incoming.review_blocking_issues:
            current.review_blocking_issues = incoming.review_blocking_issues
        if incoming.review_suggested_edits:
            current.review_suggested_edits = incoming.review_suggested_edits
        if incoming.review_frame_paths:
            current.review_frame_paths = incoming.review_frame_paths

    def _discover_rendered_video_path(self) -> str | None:
        """Discover a rendered MP4 from SDK signals or task output artifacts."""
        if self.video_output:
            return normalize_path_string(self.video_output)
        result_candidate = self._extract_video_path_from_result()
        if result_candidate:
            return result_candidate
        text_candidate = self._extract_video_path_from_text()
        if text_candidate:
            return text_candidate
        if not self._saw_completed_task_notification and not hasattr(self, "_result_message"):
            logger.debug(
                "_discover_rendered_video_path: skip filesystem scan before "
                "completion signal/result"
            )
            return None
        if not self.output_cwd:
            return None

        candidate_dirs = [
            self.output_cwd,
            self.output_cwd / "media",
            self.output_cwd / "media" / "videos",
        ]
        seen: set[Path] = set()
        candidates: list[Path] = []
        for base_dir in candidate_dirs:
            if not base_dir.exists():
                logger.debug(
                    "_discover_rendered_video_path: skip missing dir=%s",
                    str(base_dir),
                )
                continue
            dir_count = 0
            for path in base_dir.rglob("*.mp4"):
                if "partial_movie_files" in path.parts:
                    continue
                if self.output_cwd is not None:
                    segment_root = (self.output_cwd / "segments").resolve()
                    try:
                        if path.resolve().is_relative_to(segment_root):
                            continue
                    except ValueError:
                        pass
                if path.stat().st_size == 0:
                    continue
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                candidates.append(resolved)
                dir_count += 1
            logger.debug(
                "_discover_rendered_video_path: dir=%s matched=%d",
                str(base_dir),
                dir_count,
            )

        if not candidates:
            logger.debug("_discover_rendered_video_path: no mp4 found under %s", self.output_cwd)
            return None

        best = max(candidates, key=lambda p: p.stat().st_mtime)
        best_str = str(best)
        logger.debug(
            "_discover_rendered_video_path: selected %r from %d candidate(s)",
            best_str,
            len(candidates),
        )
        return best_str

    def _discover_rendered_segment_paths(self) -> list[str]:
        """Discover beat segment video assets under the task output directory."""
        if not self.output_cwd:
            return []
        discovered = discover_segment_video_paths(output_dir=str(self.output_cwd))
        logger.debug(
            "_discover_rendered_segment_paths: discovered %d segment(s)",
            len(discovered),
        )
        return discovered

    def _build_pipeline_output_from_raw(
        self,
        raw: Any,
        *,
        source: str,
    ) -> PipelineOutput:
        logger.debug("_build_pipeline_output_from_raw[%s]: raw type=%s", source, type(raw).__name__)
        if isinstance(raw, str):
            raw = json.loads(raw)
            logger.debug(
                "_build_pipeline_output_from_raw[%s]: parsed JSON, type=%s",
                source,
                type(raw).__name__,
            )
        if not isinstance(raw, dict):
            raise ValueError(f"{source} unexpected type: {type(raw).__name__}")
        validated_output = PipelineOutput.model_validate(raw)
        if validated_output.video_output:
            validated_output.video_output = self._normalize_output_path(
                validated_output.video_output
            )
        if validated_output.final_video_output:
            validated_output.final_video_output = self._normalize_output_path(
                validated_output.final_video_output
            )
        if validated_output.scene_file:
            validated_output.scene_file = self._normalize_output_path(
                validated_output.scene_file
            )
        if validated_output.audio_path:
            validated_output.audio_path = self._normalize_output_path(validated_output.audio_path)
        if validated_output.subtitle_path:
            validated_output.subtitle_path = self._normalize_output_path(
                validated_output.subtitle_path
            )
        if validated_output.bgm_path:
            validated_output.bgm_path = self._normalize_output_path(validated_output.bgm_path)
        if validated_output.segment_video_paths:
            validated_output.segment_video_paths = [
                self._normalize_output_path(path) for path in validated_output.segment_video_paths
            ]
        return validated_output

    def _normalize_output_path(self, value: str) -> str:
        normalized = normalize_path_string(value)
        path = Path(normalized)
        if not path.is_absolute() and self.output_cwd is not None:
            return str((self.output_cwd / path).resolve())
        return normalized

    def _build_scene_plan_output_from_raw(
        self,
        raw: Any,
        *,
        source: str,
    ) -> Phase1PlanningOutput:
        logger.debug(
            "_build_scene_plan_output_from_raw[%s]: raw type=%s",
            source,
            type(raw).__name__,
        )
        if isinstance(raw, str):
            raw = json.loads(raw)
            logger.debug(
                "_build_scene_plan_output_from_raw[%s]: parsed JSON, type=%s",
                source,
                type(raw).__name__,
            )
        if not isinstance(raw, dict):
            raise ValueError(f"{source} unexpected type: {type(raw).__name__}")
        return Phase1PlanningOutput.model_validate(raw)

    def _build_phase2_implementation_output_from_raw(
        self,
        raw: Any,
        *,
        source: str,
    ) -> Phase2ImplementationOutput:
        logger.debug(
            "_build_phase2_implementation_output_from_raw[%s]: raw type=%s",
            source,
            type(raw).__name__,
        )
        if isinstance(raw, str):
            raw = json.loads(raw)
            logger.debug(
                "_build_phase2_implementation_output_from_raw[%s]: parsed JSON, type=%s",
                source,
                type(raw).__name__,
            )
        if not isinstance(raw, dict):
            raise ValueError(f"{source} unexpected type: {type(raw).__name__}")
        return Phase2ImplementationOutput.model_validate(raw)

    def _build_phase2_script_draft_output_from_raw(
        self,
        raw: Any,
        *,
        source: str,
    ) -> Phase2ScriptDraftOutput:
        logger.debug(
            "_build_phase2_script_draft_output_from_raw[%s]: raw type=%s",
            source,
            type(raw).__name__,
        )
        if isinstance(raw, str):
            raw = json.loads(raw)
            logger.debug(
                "_build_phase2_script_draft_output_from_raw[%s]: parsed JSON, type=%s",
                source,
                type(raw).__name__,
            )
        if not isinstance(raw, dict):
            raise ValueError(f"{source} unexpected type: {type(raw).__name__}")
        return Phase2ScriptDraftOutput.model_validate(raw)

    def _build_pipeline_output_from_result_text(self, raw_result: str) -> PipelineOutput | None:
        """Parse compatibility fallback output from ResultMessage.result."""
        if not raw_result.strip():
            return None

        try:
            candidate = self._build_pipeline_output_from_raw(raw_result, source="result")
        except Exception:
            candidate = None

        if candidate is None:
            candidate = self._extract_pipeline_output_from_embedded_json(
                raw_result,
                source="result_embedded_json",
            )

        if candidate is None:
            video_path = self._extract_video_path(raw_result)
            if not video_path:
                return None
            candidate = PipelineOutput(
                video_output=video_path,
                scene_file=self._infer_scene_file(),
                scene_class=self._infer_scene_class(),
            )

        self._attach_result_candidate_source_code(candidate)
        return candidate

    def _extract_pipeline_output_from_embedded_json(
        self,
        text: str,
        *,
        source: str,
    ) -> PipelineOutput | None:
        """Try to recover PipelineOutput from fenced or embedded JSON in assistant text."""
        if not text.strip():
            return None

        for raw_json in self._iter_embedded_json_candidates(text):
            try:
                candidate = self._build_pipeline_output_from_raw(raw_json, source=source)
                logger.debug(
                    "_extract_pipeline_output_from_embedded_json[%s]: recovered candidate "
                    "video_output=%r",
                    source,
                    candidate.video_output,
                )
                self._attach_result_candidate_source_code(candidate)
                return candidate
            except Exception as exc:
                logger.debug(
                    "_extract_pipeline_output_from_embedded_json[%s]: candidate parse failed: %s",
                    source,
                    exc,
                )
        return None

    def _iter_embedded_json_candidates(self, text: str) -> list[str]:
        """Return possible JSON objects embedded in plain assistant/result text."""
        candidates: list[str] = []

        fenced_patterns = [
            r"```json\s*(\{.*?\})\s*```",
            r"```\s*(\{.*?\})\s*```",
        ]
        for pattern in fenced_patterns:
            for match in re.findall(pattern, text, flags=re.DOTALL | re.IGNORECASE):
                if isinstance(match, str):
                    candidates.append(match.strip())

        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
            candidates.append(text[brace_start : brace_end + 1].strip())

        # Preserve order while deduplicating.
        seen: set[str] = set()
        unique_candidates: list[str] = []
        for candidate in candidates:
            if candidate and candidate not in seen:
                seen.add(candidate)
                unique_candidates.append(candidate)
        return unique_candidates

    def _attach_result_candidate_source_code(self, candidate: PipelineOutput) -> None:
        if not candidate.scene_file:
            candidate.scene_file = self._infer_scene_file()
        if candidate.scene_file:
            candidate.scene_file = normalize_path_string(candidate.scene_file)
        if candidate.scene_file and candidate.scene_file in self._hook_state.captured_source_code:
            candidate.source_code = self._hook_state.captured_source_code[candidate.scene_file]
        if not candidate.scene_class:
            candidate.scene_class = self._infer_scene_class()

    def _extract_video_path_from_text(self) -> str | None:
        """Parse MP4 paths from the assistant's final text summary."""
        text = "\n".join(self.collected_text)
        if not text.strip():
            return None
        return self._extract_video_path(text)

    def _extract_video_path_from_result(self) -> str | None:
        result_text = getattr(getattr(self, "_result_message", None), "result", None)
        if not result_text:
            return None
        return self._extract_video_path(result_text)

    def _extract_video_path(self, text: str) -> str | None:
        if not text.strip():
            return None
        patterns = [
            r"([A-Za-z]:[\\/][^\s`\"']+?\.mp4)",
            r"(/[^`\s\"']+?\.mp4)",
        ]
        for pattern in patterns:
            for match in re.findall(pattern, text):
                normalized = normalize_path_string(match.rstrip(".,)"))
                if normalized and Path(normalized).exists():
                    logger.debug("_extract_video_path_from_text: matched %r", normalized)
                    return normalized
        return None

    def _looks_like_rendered_video(self, path_str: str) -> bool:
        """Return True only for real local mp4 outputs, not Claude temp artifacts."""
        path = Path(path_str)
        return path.suffix.lower() == ".mp4" and path.exists()

    def _infer_scene_file(self) -> str | None:
        """Infer the scene file from hook-captured Python files under the task cwd."""
        if self.scene_file:
            return normalize_path_string(self.scene_file)
        captured_paths = [
            Path(normalize_path_string(p)).resolve() for p in self._hook_state.captured_source_code
        ]
        if self.output_cwd is not None:
            scoped_paths = [p for p in captured_paths if self.output_cwd in p.parents]
            if len(scoped_paths) == 1:
                return str(scoped_paths[0])
        if len(captured_paths) == 1:
            return str(captured_paths[0])
        return None

    def _infer_scene_class(self) -> str | None:
        """Infer the scene class from source, bash history, or rendered video name."""
        if self.scene_class:
            return self.scene_class
        if self.pipeline_output and self.pipeline_output.scene_class:
            return self.pipeline_output.scene_class

        scene_file = self._infer_scene_file()
        source_code: str | None = None
        if scene_file:
            source_code = self._hook_state.captured_source_code.get(scene_file)
        if not source_code and self.pipeline_output and self.pipeline_output.source_code:
            source_code = self.pipeline_output.source_code
        if source_code:
            inferred = self._extract_scene_class_from_source(source_code)
            if inferred:
                return inferred

        for command in reversed(self._bash_commands):
            inferred = self._extract_scene_class_from_bash(command)
            if inferred:
                return inferred

        video_output = self.video_output or (
            self.pipeline_output.video_output if self.pipeline_output else None
        )
        if video_output:
            stem = Path(video_output).stem
            if stem:
                return stem
        return None

    def _extract_scene_class_from_source(self, source_code: str) -> str | None:
        match = re.search(
            r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*[\w\s,.*]*Scene[\w\s,.*]*\)\s*:",
            source_code,
            flags=re.MULTILINE,
        )
        return match.group(1) if match else None

    def _extract_scene_class_from_bash(self, command: str) -> str | None:
        match = re.search(
            r"(?:^|\s)manim(?:\.exe)?(?:\s+[^\n\r]*?)?\s+[^\s\"']+\.py\s+([A-Za-z_][A-Za-z0-9_]*)",
            command.strip(),
        )
        return match.group(1) if match else None

    def _attach_captured_source_code(self, context: str) -> None:
        """Link hook-captured source into PipelineOutput when possible."""
        if self.pipeline_output is None:
            return

        scene_file = self.pipeline_output.scene_file or self._infer_scene_file()
        if scene_file:
            self.pipeline_output.scene_file = normalize_path_string(scene_file)

        if (
            self.pipeline_output.scene_file
            and self.pipeline_output.scene_file in self._hook_state.captured_source_code
        ):
            self.pipeline_output.source_code = self._hook_state.captured_source_code[
                self.pipeline_output.scene_file
            ]
            if not self.pipeline_output.scene_class:
                self.pipeline_output.scene_class = self._infer_scene_class()
            logger.debug("%s: source code linked from hook state", context)
        else:
            logger.debug(
                "%s: scene_file=%r, hook captured keys=%s",
                context,
                self.pipeline_output.scene_file,
                list(self._hook_state.captured_source_code.keys()),
            )

    def _emit_event(self, event: PipelineEvent) -> None:
        """通过 event_callback 发射结构化事件（如已注册）。"""
        if self.event_callback is not None:
            self.event_callback(event)

    def _record_tool_failure(
        self, tool_use_id: str, error_type: str, message: str
    ) -> None:
        """记录 PostToolUseFailure Hook 注入的错误信息，供 TOOL_RESULT 配对时使用。"""
        self._tool_failures[tool_use_id] = (error_type, message)

    # ── 日志格式化方法 ──────────────────────────────────────────

    def _log_text(self, text: str) -> None:
        """记录文本内容（通常不逐行打印，避免噪音）。"""
        pass  # 文本已收集到 collected_text，不需要逐行打印

    def _log_tool_use(self, block: ToolUseBlock) -> None:
        """打印工具调用信息 + 发射 TOOL_START 结构化事件 + 记录配对。"""
        input_summary = self._summarize_input(block.input)
        logger.debug("_log_tool_use: id=%s, name=%s", block.id, block.name)
        logger.debug("_log_tool_use: summary=%s", input_summary)
        if block.name == "Bash" and isinstance(block.input, dict):
            command = str(block.input.get("command", "")).strip()
            if command:
                self._bash_commands.append(command)
        self._mark_implementation_start(block)
        # 记录到配对表
        import time as _t
        self._pending_tools[block.id] = (block.name, int(_t.time() * 1000))
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

    def _mark_implementation_start(self, block: ToolUseBlock) -> None:
        """Capture the first tool call that clearly begins code or render work."""
        if self.implementation_started:
            return

        name = block.name
        input_dict = block.input if isinstance(block.input, dict) else {}

        if name in ("Write", "Edit"):
            file_path = str(input_dict.get("file_path", "")).replace("\\", "/").lower()
            if file_path.endswith(".py") or file_path.endswith("/scene.py"):
                self.implementation_started = True
                self.implementation_start_reason = f"{name} {file_path or 'python file'}"
                return

        if name == "Bash":
            command = str(input_dict.get("command", "")).replace("\\", "/").lower()
            implementation_markers = ("scene.py", "cat >", "tee ", "python -c", "manim ")
            if any(marker in command for marker in implementation_markers):
                self.implementation_started = True
                preview = " ".join(command.split())[:120]
                self.implementation_start_reason = f"Bash {preview}"

    def _log_tool_result(self, block: ToolResultBlock) -> None:
        """打印工具执行结果 + 发射 TOOL_RESULT 结构化事件。"""
        content = block.content
        if content:
            if isinstance(content, str):
                full_content = content.replace("\n", "\\n")
                if len(full_content) > 500:
                    logger.debug(
                        "_log_tool_result: tool_use_id=%s, is_error=%s, content_length=%d",
                        block.tool_use_id,
                        block.is_error,
                        len(content),
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
                        block.tool_use_id,
                        block.is_error,
                        full_content,
                    )
            elif isinstance(content, list):
                logger.debug(
                    "_log_tool_result: tool_use_id=%s, is_error=%s, content_parts=%d",
                    block.tool_use_id,
                    block.is_error,
                    len(content),
                )
                for i, part in enumerate(content):
                    part_str = str(part)
                    preview = part_str[:300].replace("\n", "\\n")
                    logger.debug(
                        "_log_tool_result:   part[%d] type=%s, preview=%r",
                        i,
                        type(part).__name__,
                        preview,
                    )
                    if len(part_str) > 300:
                        logger.debug(
                            "_log_tool_result:   part[%d] ... (total %d chars)",
                            i,
                            len(part_str),
                        )
        else:
            logger.debug(
                "_log_tool_result: tool_use_id=%s, is_error=%s, content=None/empty",
                block.tool_use_id,
                block.is_error,
            )

        if block.is_error:
            self._print(f"  {_EMOJI['cross']} Result Error (tool_use_id={block.tool_use_id})")
        # ── 从配对表获取 name + 计算 duration ──
        import time as _t
        now_ms = int(_t.time() * 1000)
        pending = self._pending_tools.pop(block.tool_use_id, None)
        paired_name = pending[0] if pending else ""
        start_ms = pending[1] if pending else now_ms
        duration = max(0, now_ms - start_ms)
        # ── 获取 PostToolUseFailure 注入的错误分类 ──
        error_info = self._tool_failures.pop(block.tool_use_id, None)
        error_type = error_info[0] if error_info else None
        # 发射结构化事件（配对后 name 和 duration 已填充）
        self._emit_event(
            PipelineEvent(
                event_type=EventType.TOOL_RESULT,
                data=ToolResultPayload(
                    tool_use_id=block.tool_use_id,
                    name=paired_name,
                    is_error=block.is_error,
                    content=block.content if not block.is_error else None,
                    duration_ms=duration,
                    error_type=error_type,
                ),
            )
        )

    def _log_thinking(self, block: ThinkingBlock) -> None:
        """打印思考过程摘要 + 发射 THINKING 结构化事件。"""
        preview = block.thinking[:80].replace("\n", " ")
        if len(block.thinking) > 80:
            preview += "..."
        logger.debug("_log_thinking: preview=%s", preview)
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
