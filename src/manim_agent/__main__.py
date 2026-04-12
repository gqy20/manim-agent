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
import re
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
    StatusPayload,
    ThinkingPayload,
    ProgressPayload,
    ToolResultPayload,
    ToolStartPayload,
)


from .hooks import (
    _on_post_tool_use,
    _on_pre_tool_use,
    activate_hook_state,
    create_hook_state,
    reset_hook_state,
)

from .dispatcher import _EMOJI, _LOG_SEPARATOR, _MessageDispatcher

logger = logging.getLogger(__name__)


def _resolve_repo_root(cwd: str | None = None) -> Path:
    """Best-effort repo root discovery for both editable and installed package layouts."""
    marker_parts = ("plugins", "manim-production", ".codex-plugin", "plugin.json")
    candidates: list[Path] = []

    env_root = os.environ.get("MANIM_AGENT_REPO_ROOT")
    if env_root:
        candidates.append(Path(env_root).resolve())

    if cwd:
        resolved_cwd = Path(cwd).resolve()
        candidates.extend([resolved_cwd, *resolved_cwd.parents])

    module_path = Path(__file__).resolve()
    candidates.extend(module_path.parents)

    for candidate in candidates:
        if (candidate / Path(*marker_parts)).exists():
            return candidate

    return module_path.parents[2]


def _emit_status(
    event_callback: Callable[[PipelineEvent], None] | None,
    *,
    task_status: str,
    phase: str | None = None,
    message: str | None = None,
) -> None:
    """Emit a structured status event when an SSE callback is available."""
    if event_callback is None:
        return
    event_callback(
        PipelineEvent(
            event_type=EventType.STATUS,
            data=StatusPayload(
                task_status=task_status,
                phase=phase,
                message=message,
            ),
        )
    )


def _get_local_plugins(cwd: str | None = None) -> list[dict[str, str]]:
    """Return repo-local Claude plugins that should be injected into every task."""
    repo_root = _resolve_repo_root(cwd)
    plugin_dir = repo_root / "plugins" / "manim-production"
    manifest_path = plugin_dir / ".codex-plugin" / "plugin.json"
    if manifest_path.exists():
        return [{"type": "local", "path": str(plugin_dir)}]

    logger.warning("Local plugin manifest not found: %s", manifest_path)
    return []


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
    resolved_cwd = str(Path(cwd).resolve())

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
    repo_root = _resolve_repo_root(resolved_cwd)
    venv_bin_dir = repo_root / ".venv" / ("Scripts" if os.name == "nt" else "bin")
    venv_scripts = str(venv_bin_dir)
    current_path = os.environ.get("PATH", "")
    path_parts = [p for p in current_path.split(os.pathsep) if p]
    if venv_scripts not in path_parts:
        path_parts.append(venv_scripts)
    venv_env = dict(os.environ)
    venv_env["PATH"] = os.pathsep.join(path_parts)

    # ── 配置 SDK Hook 系统用于源码捕获 ──
    hooks = {
        "PreToolUse": [
            HookMatcher(
                matcher="Read|Write|Edit|Bash",
                hooks=[_on_pre_tool_use],
            ),
        ],
        "PostToolUse": [
            HookMatcher(
                matcher="Write|Edit",
                hooks=[_on_post_tool_use],
            ),
        ],
    }

    options = ClaudeAgentOptions(
        cwd=resolved_cwd,
        add_dirs=[resolved_cwd],
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
        # Claude Code's full startup path is brittle in Railway containers.
        # bare mode keeps the SDK query path lean while still supporting tool use.
        extra_args={"bare": None},
        # ── 环境变量：确保 manim 可被 Claude CLI 找到 ──
        env=venv_env,
        # ── SDK Hook 系统：替代手动 ToolUseBlock 迭代 ──
        hooks=hooks,
        plugins=_get_local_plugins(resolved_cwd),
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
        "allowed_tools=%s, plugins=%s, output_format=%s, system_prompt_len=%d",
        resolved_cwd, max_turns, options.allowed_tools,
        [plugin["path"] for plugin in options.plugins],
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


def _build_user_prompt(user_text: str) -> str:
    """Add execution-critical constraints to the user prompt."""
    normalized = user_text.strip()
    guidance = (
        "\n\nExecution requirements:\n"
        "- If the `manim-production` plugin is available, use it as the primary guide for scene planning, narration, math visualization, and final self-review.\n"
        "- For most non-trivial educational animations, use `/scene-plan` first to produce a beat-by-beat scene plan before coding.\n"
        "- After a plan exists, use `/scene-build` to implement the animation while keeping the planned beat order unless debugging requires a small change.\n"
        "- Use the `manim-production` skill as the umbrella quality guide across planning, implementation, rendering, and final review.\n"
        "- Keep every file inside the task directory only.\n"
        "- Write the main script to scene.py unless multiple files are truly necessary.\n"
        "- Use GeneratedScene as the main Manim Scene class unless the user explicitly asks otherwise.\n"
        "- Run Manim directly from the task directory with `manim ... scene.py GeneratedScene`.\n"
        "- Do not use absolute repository paths, do not cd to the repo root, and do not invoke `.venv/Scripts/python` directly.\n"
        "- Return structured_output.narration as natural Simplified Chinese unless the user explicitly requests another language.\n"
        "- Make the narration spoken and synchronized with the animation, and cover the full flow rather than collapsing into a one-sentence summary.\n"
    )
    return f"{normalized}{guidance}" if normalized else guidance.strip()


def _estimate_spoken_duration_seconds(text: str) -> float:
    """Roughly estimate spoken duration for mixed Chinese/Latin narration."""
    normalized = text.strip()
    if not normalized:
        return 0.0

    cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", normalized))
    latin_words = len(re.findall(r"[A-Za-z0-9]+", normalized))
    punctuation = len(re.findall(r"[，。！？,.!?；;：:、]", normalized))

    return (cjk_chars / 3.8) + (latin_words / 2.5) + (punctuation * 0.12)


def _narration_is_too_short_for_video(narration: str, video_duration: float | None) -> bool:
    """Heuristic used to warn when narration is likely much shorter than the render."""
    if not narration.strip() or video_duration is None or video_duration <= 0:
        return False
    estimated = _estimate_spoken_duration_seconds(narration)
    return estimated < max(4.0, video_duration * 0.45)


def _build_fallback_narration(user_text: str) -> str:
    """Build a minimal narration fallback when structured narration is missing."""
    cleaned = " ".join(user_text.split()).strip()
    if cleaned:
        return cleaned
    return "下面我们来看这个动画的主要内容。"


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
    """Run the full Claude -> TTS -> mux pipeline."""
    resolved_cwd = str(Path(cwd).resolve())
    full_system_prompt = prompts.get_prompt(
        user_text="",
        preset=preset,
        quality=quality,
        cwd=resolved_cwd,
    )
    marker = "\n\n# "
    system_prompt = full_system_prompt.split(marker, 1)[0] if marker in full_system_prompt else full_system_prompt

    options = _build_options(
        cwd=resolved_cwd,
        system_prompt=system_prompt,
        max_turns=max_turns,
        prompt_file=prompt_file,
        quality=quality,
        log_callback=log_callback,
    )
    user_prompt = _build_user_prompt(user_text)

    hook_state = create_hook_state(event_callback=event_callback)
    hook_state_token = activate_hook_state(hook_state)
    dispatcher = _MessageDispatcher(
        verbose=True,
        log_callback=log_callback,
        output_cwd=resolved_cwd,
        hook_state=hook_state,
    )
    if event_callback is not None:
        dispatcher.event_callback = event_callback

    dispatcher._print(f"\n{_LOG_SEPARATOR}")
    dispatcher._print(
        f"  Claude Agent Log                              Session: {options.session_id[:8]}..."
    )
    dispatcher._print(_LOG_SEPARATOR)
    dispatcher._print(f"  {_EMOJI['gear']} Phase 1/4: start Claude Agent SDK")
    dispatcher._print(f"  quality={quality} preset={preset} max_turns={max_turns}")
    _emit_status(
        event_callback,
        task_status="running",
        phase="init",
        message="Claude Agent SDK started",
    )

    _cli_stderr_lines: list[str] = []
    _orig_log_callback = log_callback

    def _counting_log_callback(line: str) -> None:
        _cli_stderr_lines.append(line)
        if _orig_log_callback:
            _orig_log_callback(line)

    options.stderr = _counting_log_callback

    try:
        async for message in query(prompt=user_prompt, options=options):
            dispatcher.dispatch(message)

        _report_stream_statistics(dispatcher, _cli_stderr_lines)

        if _dispatcher_ref is not None:
            _dispatcher_ref.append(dispatcher)

        dispatcher._print(f"  {_EMOJI['gear']} Phase 2/4: resolve render output")
        logger.debug(
            "run_pipeline: phase2: dispatcher.video_output before extraction = %r",
            dispatcher.video_output,
        )
        logger.debug(
            "run_pipeline: phase2: hook captured source code keys = %s",
            list(hook_state.captured_source_code.keys()),
        )
        po = dispatcher.get_pipeline_output()
        logger.debug("run_pipeline: PipelineOutput after get_pipeline_output: %r", po)
        video_output = po.video_output if po else None
        render_status_message = (
            "Resolving render output (pipeline_result -> structured output -> task_notification -> "
            "filesystem scan)"
        )
        if dispatcher.task_notification_status in {"failed", "stopped"}:
            note = (
                f"Task ended with status={dispatcher.task_notification_status} "
                f"before/while resolving output"
            )
            if dispatcher.task_notification_summary:
                note = f"{note}: {dispatcher.task_notification_summary}"
            render_status_message = note
        elif video_output:
            render_status_message = (
                "Render output resolved. Proceeding according to pipeline mode."
            )
        _emit_status(
            event_callback,
            task_status="running",
            phase="render",
            message=render_status_message,
        )
        logger.debug("run_pipeline: video_output = %r", video_output)

        if po is not None and video_output and po.duration_seconds is None:
            try:
                po.duration_seconds = await video_builder._get_duration(video_output)
            except Exception as exc:
                logger.debug("run_pipeline: unable to probe render duration for %r: %s", video_output, exc)

        if not video_output:
            dispatcher._print("")
            dispatcher._print(f"{_EMOJI['cross']} Claude did not produce a valid pipeline output.")
            dispatcher._print("  The agent may have failed to render the scene.")
            if dispatcher.task_notification_status:
                dispatcher._print(
                    f"  Task notification status: {dispatcher.task_notification_status}"
                )
            if dispatcher.task_notification_summary:
                dispatcher._print(f"  Notification summary: {dispatcher.task_notification_summary}")
            if dispatcher.task_notification_output_file:
                dispatcher._print(
                    f"  Notification output_file: {dispatcher.task_notification_output_file}"
                )
            if dispatcher.result_summary:
                s = dispatcher.result_summary
                if s.get("is_error"):
                    dispatcher._print(f"  SDK result flagged error: stop_reason={s.get('stop_reason')}")
            if dispatcher.task_notification_status == "stopped":
                dispatcher._print(
                    "  Note: task status is 'stopped', so render was interrupted."
                )
            elif dispatcher.task_notification_status == "failed":
                dispatcher._print(
                    "  Note: task status is 'failed', so render likely did not finish."
                )
            if dispatcher.result_summary:
                s = dispatcher.result_summary
                dispatcher._print(f"  Turns: {s.get('turns', '?')} | Error: {s.get('is_error', '?')}")
            collected = "\n".join(dispatcher.collected_text)
            if collected.strip():
                dispatcher._print("  --- Agent text output (first 2000 chars) ---")
                dispatcher._print(collected[:2000])
                if len(collected) > 2000:
                    dispatcher._print(f"  ... ({len(collected)} chars total)")
                dispatcher._print("  --- Output end ---")
            else:
                dispatcher._print("  (Agent produced no text output)")
            failure_phase = dispatcher.task_notification_status or "unknown"
            raise RuntimeError(
                "Claude did not produce a valid pipeline output. "
                f"Phase 2/4 outcome status={failure_phase}. "
                "The agent may have failed to render the scene."
            )

        if no_tts:
            dispatcher._print(f"\n{_EMOJI['video']} Output silent video: {video_output}")
            dispatcher._print("  [SKIP] Phase 3/4 skipped: TTS synthesis disabled by no_tts option.")
            dispatcher._print("  [SKIP] Phase 4/4 skipped: Video muxing requires TTS output and is disabled.")
            _emit_status(
                event_callback,
                task_status="running",
                phase="render",
                message="Skipping TTS and mux because no_tts=true. Returning silent render output.",
            )
            return video_output

        dispatcher._print(f"  {_EMOJI['gear']} Phase 3/4: synthesize TTS")
        _emit_status(
            event_callback,
            task_status="running",
            phase="tts",
            message="Synthesizing narration",
        )
        narration_text = (
            po.narration.strip()
            if po and po.narration and po.narration.strip()
            else _build_fallback_narration(user_text)
        )
        if po is not None and (not po.narration or not po.narration.strip()):
            po.narration = narration_text
            warning = (
                "Claude omitted structured_output.narration. "
                "Using fallback narration derived from the user request."
            )
            dispatcher._print(f"  [WARN] {warning}")
            logger.warning("run_pipeline: %s fallback=%r", warning, narration_text)
        if _narration_is_too_short_for_video(
            narration_text,
            po.duration_seconds if po is not None else None,
        ):
            warning = (
                "Narration is much shorter than the rendered video. "
                "Muxing will preserve the full animation and leave trailing silence instead of truncating it."
            )
            dispatcher._print(f"  [WARN] {warning}")
            logger.warning("run_pipeline: %s video=%r narration=%r", warning, video_output, narration_text)
        dispatcher._print(f"\n{_EMOJI['tts']} TTS in progress... (voice={voice_id}, model={model})")
        tts_result = await tts_client.synthesize(
            text=narration_text,
            voice_id=voice_id,
            model=model,
            output_dir=str(Path(output_path).parent),
        )
        dispatcher._print(f"  TTS done: {tts_result.duration_ms}ms, {tts_result.word_count} chars")

        dispatcher._print("[MUX] Phase 4/4: mux final video")
        dispatcher._print("[MUX] FFmpeg in progress... (video + audio + subtitle)")
        _emit_status(
            event_callback,
            task_status="running",
            phase="mux",
            message="Muxing final video",
        )
        final_video = await video_builder.build_final_video(
            video_path=video_output,
            audio_path=tts_result.audio_path,
            subtitle_path=tts_result.subtitle_path,
            output_path=output_path,
        )

        dispatcher._print(f"\n{_EMOJI['check']} Video generation complete: {final_video}")
        return final_video
    except Exception as exc:
        logger.debug("run_pipeline: === SDK QUERY LOOP EXCEPTION ===")
        logger.debug("run_pipeline: exception type=%s", type(exc).__name__)
        logger.debug("run_pipeline: exception message=%s", exc)
        import traceback as _tb

        for _line in _tb.format_exception(type(exc), exc, exc.__traceback__):
            for _ll in _line.rstrip().splitlines():
                logger.debug("run_pipeline: TRACE %s", _ll)
        raise
    finally:
        reset_hook_state(hook_state_token)


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
