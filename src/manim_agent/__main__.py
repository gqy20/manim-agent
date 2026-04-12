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
from . import render_review
from . import music_client
from . import tts_client
from . import video_builder
from .output_schema import PipelineOutput
from .review_schema import RenderReviewOutput
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
from . import prompt_builder, runtime_options, pipeline_gates

logger = logging.getLogger(__name__)


def _resolve_repo_root(cwd: str | None = None) -> Path:
    return runtime_options.resolve_repo_root(cwd)


def _resolve_plugin_dir(cwd: str | None = None) -> Path:
    return _resolve_repo_root(cwd) / "plugins" / "manim-production"


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
    return runtime_options.get_local_plugins(cwd)


def _select_permission_mode() -> str:
    return runtime_options.select_permission_mode()


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
        "--bgm-enabled",
        action="store_true",
        help="Generate instrumental background music and mix it under the narration.",
    )
    parser.add_argument(
        "--bgm-prompt",
        default=None,
        help="Optional custom prompt for instrumental background music generation.",
    )
    parser.add_argument(
        "--bgm-volume",
        type=float,
        default=0.12,
        help="Background music mix volume from 0.0 to 1.0 (default: 0.12).",
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
        default=80,
        help="Claude 最大交互轮次 (default: 80)",
    )

    parser.add_argument(
        "--target-duration",
        type=int,
        choices=[30, 60, 180, 300],
        default=60,
        help="Target final video duration in seconds (default: 60)",
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
    output_format: dict[str, Any] | None = None,
    use_default_output_format: bool = True,
    allowed_tools: list[str] | None = None,
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

    permission_mode = _select_permission_mode()

    resolved_allowed_tools = allowed_tools or [
        "Read",
        "Write",
        "Edit",
        "Bash",
        "Glob",
        "Grep",
    ]

    options = ClaudeAgentOptions(
        cwd=resolved_cwd,
        add_dirs=[resolved_cwd],
        system_prompt=final_system_prompt,
        permission_mode=permission_mode,
        max_turns=max_turns,
        # ── 会话隔离：每次运行使用唯一 session ID，不污染用户本地 Claude Code ──
        session_id=str(uuid.uuid4()),
        fork_session=True,
        # ── 日志回调 ──
        stderr=bound_stderr,
        # ── 结构化输出 schema ──
        output_format=(
            output_format
            if output_format is not None
            else (PipelineOutput.output_format_schema() if use_default_output_format else None)
        ),
        # ── 工具白名单：收敛攻击面，仅允许 pipeline 必需的工具（参照 Distill）──
        allowed_tools=resolved_allowed_tools,
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
        "_build_options: cwd=%s, max_turns=%s, permission_mode=%s, "
        "allowed_tools=%s, plugins=%s, output_format=%s, system_prompt_len=%d",
        resolved_cwd, max_turns, permission_mode, options.allowed_tools,
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


def _format_target_duration(seconds: int) -> str:
    """Format a target runtime for prompt guidance."""
    if seconds < 60:
        return f"{seconds} seconds"
    minutes, remainder = divmod(seconds, 60)
    if remainder == 0:
        return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"
    return f"{minutes}m {remainder}s"


def _build_default_bgm_prompt(user_text: str, preset: str, narration_text: str) -> str:
    """Build a restrained instrumental BGM prompt for narrated teaching videos."""
    preset_style = {
        "educational": "calm educational underscore, soft piano and light strings",
        "presentation": "clean modern underscore, light piano and gentle ambient textures",
        "proof": "subtle thoughtful underscore, restrained piano and low strings",
        "concept": "clear contemporary underscore, piano and marimba with light ambient texture",
        "default": "calm instrumental underscore, soft piano and light strings",
    }.get(preset, "calm instrumental underscore, soft piano and light strings")
    topic_hint = user_text.strip() or narration_text.strip() or "a narrated math explainer"
    return (
        f"{preset_style}, background music for a narrated explainer video about {topic_hint}, "
        "instrumental only, no vocals, non-distracting, low intensity, supportive, "
        "steady pacing, suitable under spoken narration"
    )


def _build_user_prompt(
    user_text: str,
    target_duration_seconds: int,
    cwd: str | None = None,
) -> str:
    """Add execution-critical constraints to the user prompt."""
    normalized = user_text.strip()
    target_duration = _format_target_duration(target_duration_seconds)
    plugin_dir = _resolve_plugin_dir(cwd)
    guidance = (
        "\n\nExecution requirements:\n"
        f"- Target final video duration: about {target_duration}.\n"
        "- Design the beat count, pacing, and narration density to land close to that target runtime.\n"
        "- Prefer shorter, more focused explanations for 30-second and 1-minute runs, and more developed walkthroughs for 3-minute and 5-minute runs.\n"
        f"- Use the runtime-injected `manim-production` plugin from `{plugin_dir}`.\n"
        "- That plugin location is a read-only runtime reference, not the writable task directory.\n"
        "- Do not use Bash, Read, ls, find, or path probes to verify whether the plugin exists.\n"
        "- Use the `scene-plan`, `scene-build`, `scene-direction`, `narration-sync`, and `render-review` skills directly through the injected plugin workflow.\n"
        "- The planning pass must be shown in Markdown with these section headings: `Mode`, `Learning Goal`, `Audience`, `Beat List`, `Narration Outline`, `Visual Risks`, and `Build Handoff`.\n"
        "- After the plan exists, implement the animation while keeping the planned beat order unless debugging requires a very small fix.\n"
        "- Do not begin writing `scene.py` until the visible planning pass is complete.\n"
        "- In structured_output, include `implemented_beats` as the ordered beat titles that were actually built.\n"
        "- In structured_output, include `build_summary` as a short summary of what the build phase implemented.\n"
        "- In structured_output, include `deviations_from_plan` as an array, even if it is empty.\n"
        "- In structured_output, include `beat_to_narration_map` with one short narration mapping line per beat.\n"
        "- In structured_output, include `narration_coverage_complete` and `estimated_narration_duration_seconds`.\n"
        "- Keep every file inside the task directory only.\n"
        "- Write the main script to scene.py unless multiple files are truly necessary.\n"
        "- Use GeneratedScene as the main Manim Scene class unless the user explicitly asks otherwise.\n"
        "- Run Manim directly from the task directory with `manim ... scene.py GeneratedScene`.\n"
        "- Do not use absolute repository paths, do not cd to the repo root, and do not invoke `.venv/Scripts/python` directly.\n"
        "- Return structured_output.narration as natural Simplified Chinese unless the user explicitly requests another language.\n"
        "- Make the narration spoken and synchronized with the animation, and cover the full flow rather than collapsing into a one-sentence summary.\n"
    )
    return f"{normalized}{guidance}" if normalized else guidance.strip()


def _build_scene_plan_prompt(
    user_text: str,
    target_duration_seconds: int,
    cwd: str | None = None,
) -> str:
    """Build a planning-only prompt that must stop after the visible plan."""
    normalized = user_text.strip()
    target_duration = _format_target_duration(target_duration_seconds)
    plugin_dir = _resolve_plugin_dir(cwd)
    guidance = (
        "\n\nPlanning pass only:\n"
        f"- Target final video duration: about {target_duration}.\n"
        f"- Use the runtime-injected `scene-plan` skill from the plugin rooted at `{plugin_dir}` and stop after producing the visible plan.\n"
        "- The plugin location is a read-only runtime reference, not the writable task directory.\n"
        "- Do not use Bash, Read, ls, find, or path probes to verify plugin files in this pass.\n"
        "- Do not write, edit, or render any code in this pass.\n"
        "- Use only lightweight reference reads if needed.\n"
        "- Return a Markdown plan with these exact section headings: `Mode`, `Learning Goal`, `Audience`, `Beat List`, `Narration Outline`, `Visual Risks`, and `Build Handoff`.\n"
        "- Keep the plan compact and implementation-ready.\n"
    )
    return f"{normalized}{guidance}" if normalized else guidance.strip()


def _build_implementation_prompt(
    user_text: str,
    target_duration_seconds: int,
    plan_text: str,
    cwd: str | None = None,
) -> str:
    """Build the implementation prompt after a planning pass has been accepted."""
    normalized = user_text.strip()
    target_duration = _format_target_duration(target_duration_seconds)
    plugin_dir = _resolve_plugin_dir(cwd)
    guidance = (
        "\n\nImplementation pass:\n"
        f"- Target final video duration: about {target_duration}.\n"
        "- The visible scene plan below is approved. Implement from it instead of creating a new plan.\n"
        f"- Continue using the runtime-injected `manim-production` plugin rooted at `{plugin_dir}`.\n"
        "- Use `scene-build`, `scene-direction`, `narration-sync`, and `render-review` through that injected plugin workflow.\n"
        "- The plugin location is a read-only runtime reference, not the writable task directory.\n"
        "- Do not use shell or filesystem probes to verify plugin files during implementation.\n"
        "- Preserve the planned beat order unless debugging requires a very small fix.\n"
        "- Do not begin with a fresh planning pass; begin implementation from the approved plan.\n"
        "- In structured_output, include `implemented_beats` as the ordered beat titles that were actually built.\n"
        "- In structured_output, include `build_summary` as a short summary of what the build phase implemented.\n"
        "- In structured_output, include `deviations_from_plan` as an array, even if it is empty.\n"
        "- In structured_output, include `beat_to_narration_map` with one short narration mapping line per beat.\n"
        "- In structured_output, include `narration_coverage_complete` and `estimated_narration_duration_seconds`.\n"
        "- Keep every file inside the task directory only.\n"
        "- Write the main script to scene.py unless multiple files are truly necessary.\n"
        "- Use GeneratedScene as the main Manim Scene class unless the user explicitly asks otherwise.\n"
        "- Run Manim directly from the task directory with `manim ... scene.py GeneratedScene`.\n"
        "- Do not use absolute repository paths, do not cd to the repo root, and do not invoke `.venv/Scripts/python` directly.\n"
        "- Return structured_output.narration as natural Simplified Chinese unless the user explicitly requests another language.\n"
        "- Make the narration spoken and synchronized with the animation, and cover the full flow rather than collapsing into a one-sentence summary.\n"
        "\nApproved visible scene plan:\n"
        f"{plan_text}\n"
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


def _merge_result_summaries(*summaries: dict[str, Any] | None) -> dict[str, Any] | None:
    """Combine phase summaries into one aggregate summary."""
    usable = [summary for summary in summaries if summary]
    if not usable:
        return None

    merged: dict[str, Any] = {
        "turns": 0,
        "cost_usd": 0.0,
        "duration_ms": 0,
        "is_error": False,
        "stop_reason": None,
        "errors": [],
    }
    saw_cost = False
    for summary in usable:
        turns = summary.get("turns")
        if isinstance(turns, int):
            merged["turns"] += turns
        duration_ms = summary.get("duration_ms")
        if isinstance(duration_ms, int):
            merged["duration_ms"] += duration_ms
        cost_usd = summary.get("cost_usd")
        if isinstance(cost_usd, (int, float)):
            merged["cost_usd"] += float(cost_usd)
            saw_cost = True
        merged["is_error"] = merged["is_error"] or bool(summary.get("is_error"))
        merged["stop_reason"] = summary.get("stop_reason") or merged["stop_reason"]
        errors = summary.get("errors") or []
        if isinstance(errors, list):
            merged["errors"].extend(errors)
    if not saw_cost:
        merged["cost_usd"] = None
    return merged


def _narration_is_too_short_for_video(narration: str, video_duration: float | None) -> bool:
    """Heuristic used to warn when narration is likely much shorter than the render."""
    if not narration.strip() or video_duration is None or video_duration <= 0:
        return False
    estimated = _estimate_spoken_duration_seconds(narration)
    return estimated < max(4.0, video_duration * 0.45)


def _allowed_duration_deviation_seconds(target_duration_seconds: int) -> float:
    """Return the acceptable runtime deviation for a requested target duration."""
    return min(45.0, max(8.0, target_duration_seconds * 0.2))


def _duration_target_issue(
    actual_duration_seconds: float | None,
    target_duration_seconds: int,
) -> str | None:
    """Return a blocking duration issue message when render length misses the target badly."""
    if actual_duration_seconds is None or actual_duration_seconds <= 0:
        return None

    allowed_deviation = _allowed_duration_deviation_seconds(target_duration_seconds)
    deviation = abs(actual_duration_seconds - target_duration_seconds)
    if deviation <= allowed_deviation:
        return None

    target_label = _format_target_duration(target_duration_seconds)
    actual_label = _format_target_duration(round(actual_duration_seconds))
    return (
        f"Rendered duration {actual_duration_seconds:.1f}s ({actual_label}) is too far from "
        f"the requested target of {target_duration_seconds}s ({target_label}). "
        f"Allowed deviation is {allowed_deviation:.1f}s."
    )


def _build_fallback_narration(user_text: str) -> str:
    """Build a minimal narration fallback when structured narration is missing."""
    cleaned = " ".join(user_text.split()).strip()
    if cleaned:
        return cleaned
    return "下面我们来看这个动画的主要内容。"


_PLAN_SECTION_HEADINGS = (
    "Mode",
    "Learning Goal",
    "Audience",
    "Beat List",
    "Narration Outline",
    "Visual Risks",
    "Build Handoff",
)
_PLAN_SKILL_SIGNATURE = "mp-scene-plan-v1"


def _has_visible_scene_plan(collected_text: list[str]) -> bool:
    """Check whether the assistant emitted the required planning scaffold."""
    if not collected_text:
        return False

    text = "\n".join(collected_text)
    matches = 0
    for heading in _PLAN_SECTION_HEADINGS:
        if re.search(
            rf"(?im)^\s*(?:#+\s*|\d+\.\s*)?{re.escape(heading)}\s*:?\s*$",
            text,
        ):
            matches += 1
    return matches >= len(_PLAN_SECTION_HEADINGS)


def _has_scene_plan_skill_signature(collected_text: list[str]) -> bool:
    """Check whether the visible plan includes the scene-plan skill canary."""
    if not collected_text:
        return False

    text = "\n".join(collected_text)
    return bool(
        re.search(
            rf"(?im)^\s*Skill Signature\s*:\s*{re.escape(_PLAN_SKILL_SIGNATURE)}\s*$",
            text,
        )
    )


def _extract_visible_scene_plan_text(collected_text: list[str], max_chars: int = 6000) -> str:
    """Return a bounded slice of assistant text for downstream review context."""
    text = "\n".join(part.strip() for part in collected_text if part and part.strip()).strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def _has_structured_build_summary(po: PipelineOutput | None) -> bool:
    """Require explicit build-phase bookkeeping in structured output."""
    if po is None:
        return False
    if not po.build_summary or not po.build_summary.strip():
        return False
    return len(po.implemented_beats) > 0


def _has_narration_sync_summary(po: PipelineOutput | None) -> bool:
    """Require explicit narration coverage metadata in structured output."""
    if po is None:
        return False
    if len(po.beat_to_narration_map) == 0:
        return False
    if po.narration_coverage_complete is not True:
        return False
    return po.estimated_narration_duration_seconds is not None


async def _run_render_review(
    *,
    user_text: str,
    plan_text: str,
    video_output: str,
    frame_paths: list[str],
    target_duration_seconds: int,
    actual_duration_seconds: float | None,
    cwd: str,
    system_prompt: str,
    quality: str,
    log_callback: Callable[[str], None] | None,
) -> RenderReviewOutput:
    """Ask Claude to review sampled render frames and return a structured verdict."""
    frame_bullets = "\n".join(f"- {path}" for path in frame_paths)
    measured_duration = (
        f"{actual_duration_seconds:.2f}s"
        if actual_duration_seconds is not None and actual_duration_seconds > 0
        else "unknown"
    )
    review_prompt = (
        "Use the `render-review` skill to inspect sampled frames from a rendered Manim video.\n"
        "Do not write, edit, or render anything in this pass. Only review the output.\n"
        "Inspect the frame image files with Read if needed.\n"
        "Mark `approved` as false if there are blocking visual issues.\n"
        "Blocking issues include: empty or title-only opening, overcrowded frame, unclear focal point, "
        "key conclusion not shown through visible change, or weak ending payoff.\n\n"
        f"Original user request:\n{user_text}\n\n"
        "Duration target:\n"
        f"- requested runtime: about {_format_target_duration(target_duration_seconds)}\n"
        f"- measured render runtime: {measured_duration}\n\n"
        "Visible plan / build context:\n"
        f"{plan_text or '(no plan text available)'}\n\n"
        f"Rendered video path:\n- {video_output}\n\n"
        "Sampled review frames:\n"
        f"{frame_bullets}\n"
    )

    review_options = _build_options(
        cwd=cwd,
        system_prompt=system_prompt,
        max_turns=12,
        quality=quality,
        log_callback=log_callback,
        output_format=RenderReviewOutput.output_format_schema(),
        allowed_tools=["Read", "Glob", "Grep"],
    )

    result_message: ResultMessage | None = None
    async for message in query(prompt=review_prompt, options=review_options):
        if isinstance(message, ResultMessage):
            result_message = message

    if result_message is None or result_message.structured_output is None:
        raise RuntimeError("Render review did not produce a structured verdict.")

    raw = result_message.structured_output
    if isinstance(raw, str):
        raw = json.loads(raw)
    return RenderReviewOutput.model_validate(raw)


async def run_pipeline(
    user_text: str,
    output_path: str,
    voice_id: str = "female-tianmei",
    model: str = "speech-2.8-hd",
    quality: str = "high",
    no_tts: bool = False,
    bgm_enabled: bool = False,
    bgm_prompt: str | None = None,
    bgm_volume: float = 0.12,
    target_duration_seconds: int = 60,
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
    bgm_volume = min(max(bgm_volume, 0.0), 1.0)
    full_system_prompt = prompts.get_prompt(
        user_text="",
        preset=preset,
        quality=quality,
        cwd=resolved_cwd,
    )
    system_prompt = full_system_prompt

    planning_options = _build_options(
        cwd=resolved_cwd,
        system_prompt=system_prompt,
        max_turns=min(max_turns, 16),
        prompt_file=prompt_file,
        quality=quality,
        log_callback=log_callback,
        use_default_output_format=False,
        allowed_tools=["Read", "Glob", "Grep"],
    )
    build_options = _build_options(
        cwd=resolved_cwd,
        system_prompt=system_prompt,
        max_turns=max_turns,
        prompt_file=prompt_file,
        quality=quality,
        log_callback=log_callback,
    )

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
        f"  Claude Agent Log                              Session: {build_options.session_id[:8]}..."
    )
    dispatcher._print(_LOG_SEPARATOR)
    dispatcher._print(f"  {_EMOJI['gear']} Phase 1/5: scene planning pass")
    dispatcher._print(
        f"  quality={quality} preset={preset} max_turns={max_turns} "
        f"target_duration={target_duration_seconds}s"
    )
    if build_options.plugins:
        plugin_labels = ", ".join(
            Path(plugin["path"]).name for plugin in build_options.plugins if plugin.get("path")
        )
        dispatcher._print(f"  [SYS] Plugins loaded: {plugin_labels}")
    if planning_options.allowed_tools:
        dispatcher._print(f"  [SYS] Allowed tools: {', '.join(planning_options.allowed_tools)}")
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

    planning_options.stderr = _counting_log_callback
    build_options.stderr = _counting_log_callback

    try:
        planning_result_summary: dict[str, Any] | None = None
        planning_prompt = _build_scene_plan_prompt(
            user_text,
            target_duration_seconds,
            resolved_cwd,
        )
        async for message in query(prompt=planning_prompt, options=planning_options):
            dispatcher.dispatch(message)
        planning_result_summary = dispatcher.result_summary

        if not _has_visible_scene_plan(dispatcher.collected_text):
            dispatcher._print("")
            dispatcher._print(
                f"{_EMOJI['cross']} Missing required scene plan before implementation."
            )
            dispatcher._print(
                "  The assistant must emit a visible planning pass with Mode, Learning Goal,"
            )
            dispatcher._print(
                "  Audience, Beat List, Narration Outline, Visual Risks, and Build Handoff"
            )
            raise RuntimeError(
                "Claude skipped the required scene-plan pass. "
                "A visible planning scaffold is mandatory before implementation."
            )

        if not _has_scene_plan_skill_signature(dispatcher.collected_text):
            dispatcher._print("")
            dispatcher._print(
                "  [WARN] Visible plan does not include the optional scene-plan signature."
            )
            dispatcher._print(
                "  Continuing because the visible plan itself is present."
            )

        plan_text = _extract_visible_scene_plan_text(dispatcher.collected_text)
        dispatcher.partial_target_duration_seconds = target_duration_seconds
        dispatcher.partial_plan_text = plan_text
        dispatcher._print("  [PLAN] Visible scene plan accepted.")
        dispatcher._print(f"  {_EMOJI['gear']} Phase 2/5: implementation pass")
        if build_options.allowed_tools:
            dispatcher._print(f"  [SYS] Allowed tools: {', '.join(build_options.allowed_tools)}")
        _emit_status(
            event_callback,
            task_status="running",
            phase="scene",
            message="Visible scene plan accepted. Beginning implementation pass.",
        )

        user_prompt = _build_implementation_prompt(
            user_text,
            target_duration_seconds,
            plan_text,
            resolved_cwd,
        )
        async for message in query(prompt=user_prompt, options=build_options):
            dispatcher.dispatch(message)
            if dispatcher.implementation_started:
                if not _has_visible_scene_plan(dispatcher.collected_text):
                    dispatcher._print("")
                    dispatcher._print(
                        f"{_EMOJI['cross']} Blocking implementation before visible scene plan."
                    )
                    if dispatcher.implementation_start_reason:
                        dispatcher._print(
                            "  First implementation step: "
                            f"{dispatcher.implementation_start_reason}"
                        )
                    dispatcher._print(
                        "  Emit the required planning scaffold before writing scene.py, "
                        "editing Python files, or running Manim."
                    )
                    raise RuntimeError(
                        "Claude began implementation before emitting the required visible scene-plan pass."
                    )
        _report_stream_statistics(dispatcher, _cli_stderr_lines)

        if _dispatcher_ref is not None:
            _dispatcher_ref.append(dispatcher)

        result_summary = _merge_result_summaries(
            planning_result_summary,
            dispatcher.result_summary,
        )
        if result_summary is not None:
            dispatcher.partial_run_turns = result_summary.get("turns")
            dispatcher.partial_run_duration_ms = result_summary.get("duration_ms")
            dispatcher.partial_run_cost_usd = result_summary.get("cost_usd")
        dispatcher.partial_run_tool_use_count = dispatcher.tool_use_count
        dispatcher.partial_run_tool_stats = dict(dispatcher.tool_stats)

        dispatcher._print(f"  {_EMOJI['gear']} Phase 3/5: resolve render output")
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

        if po is not None:
            if result_summary is not None:
                po.run_turns = result_summary.get("turns")
                po.run_duration_ms = result_summary.get("duration_ms")
                po.run_cost_usd = result_summary.get("cost_usd")
            po.run_tool_use_count = dispatcher.tool_use_count
            po.run_tool_stats = dict(dispatcher.tool_stats)
            po.target_duration_seconds = target_duration_seconds
            po.plan_text = plan_text
            dispatcher.partial_build_summary = po.build_summary
            dispatcher.partial_deviations_from_plan = list(po.deviations_from_plan)
            dispatcher.partial_beat_to_narration_map = list(po.beat_to_narration_map)
            dispatcher.partial_narration_coverage_complete = po.narration_coverage_complete
            dispatcher.partial_estimated_narration_duration_seconds = (
                po.estimated_narration_duration_seconds
            )

        needs_build_summary = not _has_structured_build_summary(po)
        needs_narration_summary = not _has_narration_sync_summary(po)
        if video_output and (needs_build_summary or needs_narration_summary):
            dispatcher._print("  [REPAIR] Structured output is incomplete. Running a no-tools repair pass.")
            repair_prompt = prompt_builder.build_output_repair_prompt(
                user_text,
                target_duration_seconds,
                plan_text=plan_text,
                partial_output=dispatcher.get_persistable_pipeline_output(),
                video_output=video_output,
            )
            repair_options = _build_options(
                cwd=resolved_cwd,
                system_prompt=system_prompt,
                max_turns=6,
                prompt_file=prompt_file,
                quality=quality,
                log_callback=_counting_log_callback,
                allowed_tools=[],
            )
            async for message in query(prompt=repair_prompt, options=repair_options):
                dispatcher.dispatch(message)

            repair_result_summary = dispatcher.result_summary
            result_summary = _merge_result_summaries(result_summary, repair_result_summary)
            po = dispatcher.get_pipeline_output()
            if po is not None:
                if result_summary is not None:
                    po.run_turns = result_summary.get("turns")
                    po.run_duration_ms = result_summary.get("duration_ms")
                    po.run_cost_usd = result_summary.get("cost_usd")
                po.run_tool_use_count = dispatcher.tool_use_count
                po.run_tool_stats = dict(dispatcher.tool_stats)
                po.target_duration_seconds = target_duration_seconds
                po.plan_text = plan_text
                dispatcher.partial_build_summary = po.build_summary
                dispatcher.partial_deviations_from_plan = list(po.deviations_from_plan)
                dispatcher.partial_beat_to_narration_map = list(po.beat_to_narration_map)
                dispatcher.partial_narration_coverage_complete = po.narration_coverage_complete
                dispatcher.partial_estimated_narration_duration_seconds = (
                    po.estimated_narration_duration_seconds
                )

        if not _has_structured_build_summary(po):
            warning = (
                "Claude skipped the scene-build summary. "
                "Continuing with partial structured output because a render exists."
            )
            dispatcher._print(f"  [WARN] {warning}")
            logger.warning("run_pipeline: %s", warning)

        if not _has_narration_sync_summary(po):
            warning = (
                "Claude skipped the narration-sync summary. "
                "Continuing because narration metadata can be incomplete without blocking delivery."
            )
            dispatcher._print(f"  [WARN] {warning}")
            logger.warning("run_pipeline: %s", warning)

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
                f"Phase 3/5 outcome status={failure_phase}. "
                "The agent may have failed to render the scene."
            )

        dispatcher._print("  [REVIEW] Sampling render frames for quality review")
        _emit_status(
            event_callback,
            task_status="running",
            phase="render",
            message="Reviewing sampled frames before final success",
        )
        review_frames = await render_review.extract_review_frames(
            video_output,
            resolved_cwd,
        )
        review_result: RenderReviewOutput | None = None
        review_warning: str | None = None
        try:
            review_result = await _run_render_review(
                user_text=user_text,
                plan_text=plan_text,
                video_output=video_output,
                frame_paths=review_frames,
                target_duration_seconds=target_duration_seconds,
                actual_duration_seconds=po.duration_seconds if po is not None else None,
                cwd=resolved_cwd,
                system_prompt=system_prompt,
                quality=quality,
                log_callback=log_callback,
            )
        except RuntimeError as exc:
            if "structured verdict" not in str(exc):
                raise
            review_warning = (
                "Render review did not produce a structured verdict. "
                "Continuing because review formatting can be incomplete without blocking delivery."
            )
            dispatcher._print(f"  [WARN] {review_warning}")
            logger.warning("run_pipeline: %s", review_warning)

        if review_result is not None:
            dispatcher._print(f"  [REVIEW] {review_result.summary}")
            if review_result.blocking_issues:
                for issue in review_result.blocking_issues:
                    dispatcher._print(f"  [REVIEW][BLOCK] {issue}")
            if review_result.suggested_edits:
                for edit in review_result.suggested_edits:
                    dispatcher._print(f"  [REVIEW][FIX] {edit}")
            if po is not None:
                po.review_summary = review_result.summary
                po.review_approved = review_result.approved
                po.review_blocking_issues = list(review_result.blocking_issues)
                po.review_suggested_edits = list(review_result.suggested_edits)
                po.review_frame_paths = list(review_frames)
            dispatcher.partial_review_summary = review_result.summary
            dispatcher.partial_review_approved = review_result.approved
            dispatcher.partial_review_blocking_issues = list(review_result.blocking_issues)
            dispatcher.partial_review_suggested_edits = list(review_result.suggested_edits)
            dispatcher.partial_review_frame_paths = list(review_frames)
            if not review_result.approved:
                raise RuntimeError(
                    "Rendered video failed the render-review gate. "
                    + "; ".join(review_result.blocking_issues or [review_result.summary])
                )
        else:
            if po is not None:
                po.review_summary = review_warning
                po.review_approved = None
                po.review_blocking_issues = []
                po.review_suggested_edits = []
                po.review_frame_paths = list(review_frames)
            dispatcher.partial_review_summary = review_warning
            dispatcher.partial_review_approved = None
            dispatcher.partial_review_blocking_issues = []
            dispatcher.partial_review_suggested_edits = []
            dispatcher.partial_review_frame_paths = list(review_frames)

        duration_issue = _duration_target_issue(
            po.duration_seconds if po is not None else None,
            target_duration_seconds,
        )
        if duration_issue is not None:
            dispatcher._print(f"  [WARN] {duration_issue}")
            logger.warning("run_pipeline: duration target miss: %s", duration_issue)
        if duration_issue is None and po is not None and po.duration_seconds is not None:
            dispatcher._print(
                "  [REVIEW] Duration check passed: "
                f"{po.duration_seconds:.1f}s vs target {target_duration_seconds}s"
            )

        if no_tts:
            if po is not None:
                po.final_video_output = video_output
            dispatcher._print(f"\n{_EMOJI['video']} Output silent video: {video_output}")
            dispatcher._print("  [SKIP] Phase 4/5 skipped: TTS synthesis disabled by no_tts option.")
            dispatcher._print("  [SKIP] Phase 5/5 skipped: Video muxing requires TTS output and is disabled.")
            _emit_status(
                event_callback,
                task_status="running",
                phase="render",
                message="Skipping TTS and mux because no_tts=true. Returning silent render output.",
            )
            return video_output

        dispatcher._print(f"  {_EMOJI['gear']} Phase 4/5: synthesize TTS")
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
        if po is not None:
            po.audio_path = tts_result.audio_path or None
            po.subtitle_path = tts_result.subtitle_path or None
            po.extra_info_path = tts_result.extra_info_path or None
            po.tts_mode = tts_result.mode
            po.tts_duration_ms = tts_result.duration_ms
            po.tts_word_count = tts_result.word_count
            po.tts_usage_characters = tts_result.usage_characters
        transport_label = "SYNC HTTP" if tts_result.mode == "sync" else "ASYNC LONG-TEXT"
        subtitle_label = "embedded captions ready" if tts_result.subtitle_path else "audio-only mux"
        dispatcher._print(f"  [TTS] Transport: {transport_label}")
        dispatcher._print(f"  [TTS] Output mode: {subtitle_label}")
        dispatcher._print(f"  TTS done: {tts_result.duration_ms}ms, {tts_result.word_count} chars")

        resolved_bgm_prompt = None
        bgm_result = None
        if bgm_enabled:
            resolved_bgm_prompt = (
                bgm_prompt.strip()
                if bgm_prompt and bgm_prompt.strip()
                else _build_default_bgm_prompt(user_text, preset, narration_text)
            )
            dispatcher._print("  [BGM] Generating instrumental background music")
            try:
                bgm_result = await music_client.generate_instrumental(
                    prompt=resolved_bgm_prompt,
                    output_dir=str(Path(output_path).parent),
                    model="music-2.6",
                )
                dispatcher._print(
                    "  [BGM] Done: "
                    f"path={bgm_result.audio_path} volume={bgm_volume:.2f}"
                )
            except Exception as exc:
                warning = (
                    "Background music generation failed. "
                    "Falling back to narration-only final mux."
                )
                dispatcher._print(f"  [WARN] {warning}")
                logger.warning("run_pipeline: %s error=%s", warning, exc)
        if po is not None:
            po.bgm_path = bgm_result.audio_path if bgm_result is not None else None
            po.bgm_prompt = resolved_bgm_prompt
            po.bgm_duration_ms = bgm_result.duration_ms if bgm_result is not None else None
            po.bgm_volume = bgm_volume if bgm_result is not None else None
            po.audio_mix_mode = "voice_with_bgm" if bgm_result is not None else "voice_only"

        dispatcher._print("[MUX] Phase 5/5: mux final video")
        dispatcher._print(
            "[MUX] FFmpeg in progress... "
            f"({'video + narration + bgm + subtitle' if bgm_result is not None else 'video + audio + subtitle'})"
        )
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
            bgm_path=bgm_result.audio_path if bgm_result is not None else None,
            bgm_volume=bgm_volume,
        )
        if po is not None:
            po.final_video_output = final_video

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
            bgm_enabled=args.bgm_enabled,
            bgm_prompt=args.bgm_prompt,
            bgm_volume=args.bgm_volume,
            target_duration_seconds=args.target_duration,
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
