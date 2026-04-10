"""CLI 入口：python -m manim_agent

解析命令行参数，编排 Claude Agent SDK → TTS → FFmpeg 的完整 pipeline。
充分利用 SDK 消息流中的 ToolUse / ToolResult / ResultMessage 等结构化信息，
提供实时工作日志输出。通过 session_id + fork_session 实现与本地 Claude Code 的会话隔离。
"""

import argparse
import asyncio
import logging
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

load_dotenv()

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    Message,
    RateLimitEvent,
    ResultMessage,
    TaskNotificationMessage,
    TaskProgressMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    query,
)

from . import prompts
from . import tts_client
from . import video_builder

logger = logging.getLogger(__name__)


# ── 日志样式常量 ───────────────────────────────────────────────

_LOG_SEPARATOR = "═" * 58
_EMOJI = {
    "write": "\u270f\ufe0f",       # ✏️
    "bash": "\U0001f528",         # 🔨
    "read": "\U0001f4cf",          # 📸
    "think": "\U0001f4ad",        # 💭
    "video": "\U0001f3a5",        # 📤
    "check": "\u2705",             # ✅
    "cross": "\u274c",            # ❌
    "tts": "\U0001f3a4",           # 🎙️
    "film": "\U0001f3ac",          # 🎬
    "chart": "\U0001f4ca",          # 📊
    "gear": "\u2699\ufe0f",         # ⚙
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

    将当前内联的 hasattr 逻辑替换为基于 isinstance 的类型安全分发，
    完整利用 SDK 提供的 ToolUseBlock / ToolResultBlock / ResultMessage /
    RateLimitEvent / TaskProgressMessage 等消息类型。
    """

    def __init__(
        self,
        verbose: bool = True,
        log_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.verbose = verbose
        self.log_callback = log_callback
        self.turn_count = 0
        self.tool_use_count = 0
        self.tool_stats: dict[str, int] = {}
        self.collected_text: list[str] = []
        self.video_output: str | None = None
        self.scene_file: str | None = None
        self.scene_class: str | None = None
        self.result_summary: dict[str, Any] | None = None

    # ── 公共接口 ──────────────────────────────────────────────

    def dispatch(self, message: Message) -> None:
        """根据消息类型路由到对应处理器。"""
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
        # UserMessage / SystemMessage / StreamEvent 暂不处理

    def get_video_output(self) -> str | None:
        """返回提取到的视频输出路径（可能为 None）。"""
        if self.video_output is None:
            self._extract_video_output()
        return self.video_output

    # ── 消息处理器 ──────────────────────────────────────────────

    def _handle_assistant(self, msg: AssistantMessage) -> None:
        """处理 AssistantMessage，遍历所有 content block。"""
        for block in msg.content:
            if isinstance(block, TextBlock):
                self._log_text(block.text)
                self.collected_text.append(block.text)

            elif isinstance(block, ToolUseBlock):
                self._log_tool_use(block)
                self.tool_use_count += 1
                name = block.name
                self.tool_stats[name] = self.tool_stats.get(name, 0) + 1

            elif isinstance(block, ToolResultBlock):
                self._log_tool_result(block)

            elif isinstance(block, ThinkingBlock):
                self._log_thinking(block)

    def _handle_result(self, msg: ResultMessage) -> None:
        """处理 ResultMessage，记录会话摘要。"""
        self.result_summary = {
            "turns": msg.num_turns,
            "cost_usd": msg.total_cost_usd,
            "duration_ms": msg.duration_ms,
            "is_error": msg.is_error,
            "stop_reason": msg.stop_reason,
            "errors": msg.errors,
        }
        self._log_result_summary()

    def _handle_rate_limit(self, event: RateLimitEvent) -> None:
        """处理限流事件。"""
        info = event.rate_limit_info
        status_icon = _EMOJI["check"] if info.status == "allowed" else _EMOJI["cross"]
        self._print(f"  {status_icon} RateLimit: {info.status} "
                     f"(utilization={info.utilization:.0%})")

    def _handle_task_progress(self, msg: TaskProgressMessage) -> None:
        """处理任务进度消息。"""
        usage = msg.usage
        self._print(f"  {_EMOJI['gear']} Progress: "
                     f"{usage['total_tokens']} tokens, "
                     f"{usage['tool_uses']} tool_uses, "
                     f"{usage['duration_ms'] // 1000}s")

    def _handle_task_notification(self, msg: TaskNotificationMessage) -> None:
        """处理任务完成/失败通知。"""
        icon = _EMOJI["check"] if msg.status == "completed" else _EMOJI["cross"]
        self._print(f"  {icon} Task {msg.status}: {msg.summary}")

    # ── VIDEO_OUTPUT 提取 ─────────────────────────────────────────

    def _extract_video_output(self) -> None:
        """从收集的文本中提取结构化标记。"""
        last_video_output = None
        for text in self.collected_text:
            for line in text.splitlines():
                if line.startswith("VIDEO_OUTPUT:"):
                    last_video_output = line.split(":", 1)[1].strip()
                elif line.startswith("SCENE_FILE:"):
                    self.scene_file = line.split(":", 1)[1].strip()
                elif line.startswith("SCENE_CLASS:"):
                    self.scene_class = line.split(":", 1)[1].strip()

        self.video_output = last_video_output

    # ── 日志格式化方法 ──────────────────────────────────────────

    def _log_text(self, text: str) -> None:
        """记录文本内容（通常不逐行打印，避免噪音）。"""
        pass  # 文本已收集到 collected_text，不需要逐行打印

    def _log_tool_use(self, block: ToolUseBlock) -> None:
        """打印工具调用信息。"""
        icon = _EMOJI.get(block.name.lower(), "\u25b6")
        input_summary = self._summarize_input(block.input)
        self._print(f"  {icon} {block.name} \u2192 {input_summary}")

    def _log_tool_result(self, block: ToolResultBlock) -> None:
        """打印工具执行结果。"""
        if block.is_error:
            self._print(f"  {_EMOJI['cross']} Result Error "
                         f"(tool_use_id={block.tool_use_id})")
        # 成功结果通常静默（避免日志刷屏）

    def _log_thinking(self, block: ThinkingBlock) -> None:
        """打印思考过程摘要。"""
        preview = block.thinking[:80].replace("\n", " ")
        if len(block.thinking) > 80:
            preview += "..."
        self._print(f"  {_EMOJI['think']} {preview}")

    def _log_result_summary(self) -> None:
        """打印会话摘要。"""
        s = self.result_summary
        if not s:
            return

        self._print("")
        self._print(f"{_LOG_SEPARATOR}")
        self._print(f"{_EMOJI['chart']} Session Summary:")
        self._print(f"  Turns: {s['turns']} | "
                     f"Cost: ${s['cost_usd']:.4f} | "
                     f"Duration: {s['duration_ms'] // 1000}s")
        if self.tool_stats:
            tools_str = ", ".join(
                f"{k}\u00d7{v}" for k, v in self.tool_stats.items()
            )
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
                v_str = v_str[:max_len - 3] + "..."
            parts.append(f"{k}={v_str}")
        result = " ".join(parts)
        if len(result) > max_len:
            result = result[:max_len - 3] + "..."
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
        "-o", "--output",
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
    d = _MessageDispatcher(verbose=False)
    d.collected_text = [text]
    d._extract_video_output()
    return {
        "video_output_path": d.video_output,
        "scene_file": d.scene_file,
        "scene_class": d.scene_class,
    }


# ── Options 构建 ────────────────────────────────────────────────


def _stderr_handler(line: str) -> None:
    """将 CLI 子进程的 stderr 原始输出有选择地转发。

    仅转发包含错误/警告信息的行，过滤噪音。
    """
    lower = line.lower()
    if any(kw in lower for kw in ("error", "warning", "fail", "exception")):
        print(f"  [CLI] {line.strip()}", file=sys.stderr)


def _build_options(
    cwd: str,
    system_prompt: str | None,
    max_turns: int,
    prompt_file: str | None = None,
    quality: str = "high",
) -> ClaudeAgentOptions:
    """构建 ClaudeAgentOptions，含会话隔离和日志回调。

    Args:
        cwd: 工作目录。
        system_prompt: 系统提示词（优先级最高，若提供则直接使用）。
        max_turns: 最大交互轮次。
        prompt_file: 自定义提示词文件路径。
        quality: 渲染质量 ("high" | "medium" | "low")，
            仅在未提供 system_prompt 和 prompt_file 时生效。

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

    return ClaudeAgentOptions(
        cwd=cwd,
        system_prompt=final_system_prompt,
        permission_mode="acceptEdits",
        max_turns=max_turns,
        # ── 会话隔离：每次运行使用唯一 session ID，不污染用户本地 Claude Code ──
        session_id=str(uuid.uuid4()),
        fork_session=True,
        # ── 日志回调 ──
        stderr=_stderr_handler,
    )


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
    )

    # 用户提示词直接传递
    user_prompt = user_text

    # 2. 创建 dispatcher 并消费消息流
    dispatcher = _MessageDispatcher(verbose=True, log_callback=log_callback)
    dispatcher._print(f"\n{_LOG_SEPARATOR}")
    dispatcher._print(f"  Claude Agent 工作日志                              "
                   f"Session: {options.session_id[:8]}...")
    dispatcher._print(_LOG_SEPARATOR)

    async for message in query(prompt=user_prompt, options=options):
        dispatcher.dispatch(message)

    # 3. 从 dispatcher 提取结果
    video_output = dispatcher.get_video_output()

    if not video_output:
        dispatcher._print("")
        dispatcher._print(f"{_EMOJI['cross']} Claude 未生成 VIDEO_OUTPUT 标记。")
        dispatcher._print(f"  Agent 可能未能成功渲染场景。")
        if dispatcher.result_summary:
            s = dispatcher.result_summary
            dispatcher._print(f"  Turns: {s.get('turns', '?')} | "
                         f"Error: {s.get('is_error', '?')}")
        raise RuntimeError(
            "Claude did not produce a VIDEO_OUTPUT marker. "
            "The agent may have failed to render the scene."
        )

    # 4-5. TTS + FFmpeg（可选）
    if no_tts:
        dispatcher._print(f"\n{_EMOJI['video']} 输出静音视频: {video_output}")
        return video_output

    # TTS 合成
    dispatcher._print(f"\n{_EMOJI['tts']} TTS 合成中... "
                   f"(voice={voice_id}, model={model})")
    tts_result = await tts_client.synthesize(
        text=user_text,
        voice_id=voice_id,
        model=model,
        output_dir=str(Path(output_path).parent),
    )
    dispatcher._print(f"  TTS 完成: {tts_result.duration_ms}ms, "
                 f"{tts_result.word_count} chars")

    # FFmpeg 合成
    dispatcher._print(f"{_EMOJI['film']} FFmpeg 合成中... "
                   f"(video + audio + subtitle)")
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
        output = await run_pipeline(
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
