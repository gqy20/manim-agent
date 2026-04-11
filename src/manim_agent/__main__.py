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
    HookMatcher,
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
    query,
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


from .hooks import _hook_state, _on_post_tool_use

from .dispatcher import _EMOJI, _LOG_SEPARATOR, _MessageDispatcher

logger = logging.getLogger(__name__)


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
    logger.debug(
        "_build_options: cwd=%s, max_turns=%s, permission_mode=bypassPermissions, "
        "allowed_tools=%s, output_format=%s, system_prompt_len=%d",
        cwd, max_turns, options.allowed_tools,
        "set" if options.output_format else "None",
        len(final_system_prompt) if final_system_prompt else 0,
    )
    return options


# ── Pipeline 编排 ─────────────────────────────────────────────


def _report_stream_statistics(
    dispatcher: "_MessageDispatcher",
    cli_stderr_lines: list[str],
) -> None:
    """Log message stream and CLI stderr statistics after query loop completes."""
    logger.debug(
        "MESSAGE STREAM END SUMMARY: total=%s type_dist=%s assistant=%s",
        dispatcher._msg_count, dispatcher._msg_type_stats,
        dispatcher._assistant_msg_count,
    )
    logger.debug("tool_use_count=%s tool_stats=%s", dispatcher.tool_use_count, dispatcher.tool_stats)
    logger.debug("collected_text blocks=%s", len(dispatcher.collected_text))
    if dispatcher.collected_text:
        total_chars = sum(len(t) for t in dispatcher.collected_text)
        logger.debug("collected_text total chars=%s", total_chars)
    logger.debug("video_output (early)=%r", dispatcher.video_output)
    logger.debug("pipeline_output (early)=%s", "set" if dispatcher.pipeline_output is not None else "None")

    # CLI stderr statistics
    if cli_stderr_lines:
        logger.debug("CLI stderr lines captured = %d", len(cli_stderr_lines))
        err_keywords = ("error", "warn", "fail", "exception", "exit", "kill")
        for sline in cli_stderr_lines:
            slower = sline.lower()
            if any(kw in slower for kw in err_keywords):
                logger.debug("CLI STDERR: %s", sline[:300])
        if len(cli_stderr_lines) <= 10:
            for sline in cli_stderr_lines:
                logger.debug("CLI STDERR(all): %s", sline[:200])


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
    dispatcher = _MessageDispatcher(
        verbose=True,
        log_callback=log_callback,
        output_cwd=cwd,
    )
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
        logger.debug(' run_pipeline: === SDK QUERY LOOP EXCEPTION ===')
        logger.debug(' run_pipeline: exception type={type(exc).__name__}')
        logger.debug(' run_pipeline: exception message={exc}')
        import traceback as _tb
        for _line in _tb.format_exception(type(exc), exc, exc.__traceback__):
            for _ll in _line.rstrip().splitlines():
                logger.debug(' run_pipeline: TRACE {_ll}')
        raise  # re-raise so existing error handling works

    # ── 盲区5: 消息流结束总结 ──
    _report_stream_statistics(dispatcher, _cli_stderr_lines)


    # 将 dispatcher 传给调用方（用于提取 pipeline_output 等元数据）
    if _dispatcher_ref is not None:
        _dispatcher_ref.append(dispatcher)

    # 3. 从 dispatcher 提取结果
    # ── 阶段标记：SDK 对话结束，提取输出 ──
    dispatcher._print(f"  {_EMOJI['gear']} Phase 2/4: 提取渲染结果...")
    dispatcher._print(
        logger.debug(' run_pipeline: dispatcher.video_output (before get_pipeline_output) = {dispatcher.video_output!r}')
    )
    dispatcher._print(
        logger.debug(' run_pipeline: hook captured source code keys = {list(_hook_state.captured_source_code.keys())}')
    )
    po = dispatcher.get_pipeline_output()
    logger.debug(' run_pipeline: PipelineOutput after get_pipeline_output: {po!r}')
    video_output = dispatcher.get_video_output()
    dispatcher._print(
        logger.debug(' run_pipeline: video_output from get_video_output = {video_output!r}')
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
