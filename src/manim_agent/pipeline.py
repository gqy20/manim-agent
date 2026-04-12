"""Pipeline 编排：Claude Agent SDK → TTS → FFmpeg 的完整执行流程。

包含 run_pipeline() 及其全部辅助函数（options 构建、prompt 包装、
解说生成、render review、PO 元数据填充等）。
"""

import asyncio
import functools
import json
import logging
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Callable, cast

from claude_agent_sdk import (
    ClaudeAgentOptions,
    HookMatcher,
    ResultMessage,
    query,
)

from . import prompts, prompt_builder, render_review, runtime_options
from . import music_client, tts_client, video_builder
from .output_schema import PipelineOutput
from .review_schema import RenderReviewOutput
from .pipeline_events import (
    EventType,
    PipelineEvent,
    StatusPayload,
)
from .hooks import (
    _on_post_tool_use,
    _on_pre_tool_use,
    activate_hook_state,
    create_hook_state,
    reset_hook_state,
)
from .dispatcher import _EMOJI, _LOG_SEPARATOR, _MessageDispatcher
from .pipeline_gates import (
    PLAN_SECTION_HEADINGS,
    PLAN_SKILL_SIGNATURE,
    allowed_duration_deviation_seconds,
    build_fallback_narration,
    duration_target_issue,
    estimate_spoken_duration_seconds,
    extract_visible_scene_plan_text,
    has_narration_sync_summary,
    has_scene_plan_skill_signature,
    has_structured_build_summary,
    has_visible_scene_plan,
    merge_result_summaries,
    narration_is_too_short_for_video,
)
from .prompt_builder import format_target_duration

logger = logging.getLogger(__name__)


# ── 路径解析 ──────────────────────────────────────────────────────


def _resolve_repo_root(cwd: str | None = None) -> Path:
    return runtime_options.resolve_repo_root(cwd)


def _resolve_plugin_dir(cwd: str | None = None) -> Path:
    return _resolve_repo_root(cwd) / "plugins" / "manim-production"


# ── 事件发射 ──────────────────────────────────────────────────────


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


# ── Runtime options 代理 ──────────────────────────────────────────


def _get_local_plugins(cwd: str | None = None) -> list[dict[str, str]]:
    return runtime_options.get_local_plugins(cwd)


def _select_permission_mode() -> str:
    return runtime_options.select_permission_mode()


# ── Options 构建 ───────────────────────────────────────────────────


def _stderr_handler(
    line: str,
    *,
    log_callback: Callable[[str], None] | None = None,
) -> None:
    """将 CLI 子进程的 stderr 输出转发到终端和可选的 SSE 回调。"""
    stripped = line.strip()
    if log_callback is not None:
        log_callback(f"[CLI] {stripped}")
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
    """构建 ClaudeAgentOptions，含会话隔离和日志回调。"""
    resolved_cwd = str(Path(cwd).resolve())

    if prompt_file and Path(prompt_file).exists():
        final_system_prompt = Path(prompt_file).read_text(encoding="utf-8")
    elif system_prompt:
        final_system_prompt = system_prompt
    else:
        final_system_prompt = prompts.SYSTEM_PROMPT.replace(
            "-qh", prompts.QUALITY_FLAGS.get(quality, "-qh")
        )

    bound_stderr = functools.partial(_stderr_handler, log_callback=log_callback)

    repo_root = _resolve_repo_root(resolved_cwd)
    venv_bin_dir = repo_root / ".venv" / ("Scripts" if os.name == "nt" else "bin")
    venv_scripts = str(venv_bin_dir)
    current_path = os.environ.get("PATH", "")
    path_parts = [p for p in current_path.split(os.pathsep) if p]
    if venv_scripts not in path_parts:
        path_parts.append(venv_scripts)
    venv_env = dict(os.environ)
    venv_env["PATH"] = os.pathsep.join(path_parts)

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
        "Read", "Write", "Edit", "Bash", "Glob", "Grep",
    ]

    options = ClaudeAgentOptions(
        cwd=resolved_cwd,
        add_dirs=[resolved_cwd],
        system_prompt=final_system_prompt,
        permission_mode=permission_mode,
        max_turns=max_turns,
        session_id=str(uuid.uuid4()),
        fork_session=True,
        stderr=bound_stderr,
        output_format=(
            output_format
            if output_format is not None
            else (PipelineOutput.output_format_schema() if use_default_output_format else None)
        ),
        allowed_tools=resolved_allowed_tools,
        extra_args={"bare": None},
        env=venv_env,
        hooks=hooks,
        plugins=_get_local_plugins(resolved_cwd),
        enable_file_checkpointing=True,
    )

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


# ── 统计报告 ──────────────────────────────────────────────────────


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


# ── BGM Prompt ────────────────────────────────────────────────────


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


# ── Prompt 包装（注入运行时插件路径）────────────────────────────


def _build_scene_plan_prompt(
    user_text: str,
    target_duration_seconds: int,
    cwd: str | None = None,
) -> str:
    """Build a planning-only prompt that must stop after the visible plan."""
    normalized = user_text.strip()
    target_duration = format_target_duration(target_duration_seconds)
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
    target_duration = format_target_duration(target_duration_seconds)
    plugin_dir = _resolve_plugin_dir(cwd)
    guidance = (
        "\n\nImplementation pass:\n"
        f"- Target final video duration: about {target_duration}.\n"
        "- The visible scene plan below is approved. Implement from it instead of creating a new plan.\n"
        f"- Continue using the runtime-injected `manim-production` plugin rooted at `{plugin_dir}`.\n"
        "- Use `scene-build`, `scene-direction`, `layout-safety`, `narration-sync`, and `render-review` through that injected plugin workflow.\n"
        "- Use `layout-safety` as an advisory audit for dense beats and interpret warnings with visual judgment.\n"
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


# ── 解说质量检测与模板兜底 ──────────────────────────────────────


def _looks_like_spoken_narration(text: str) -> bool:
    """Heuristic check: does text look like spoken Chinese narration vs instructions?

    Returns True if the text appears to be genuine spoken narration.
    Returns False if it looks like a user request, topic title, or instruction.
    """
    stripped = text.strip()
    if not stripped:
        return False

    if len(stripped) < 15:
        return False

    garbage_patterns = [
        r"请制作", r"请帮我", r"生成一段", r"创建一个",
        r"用动画演示", r"可视化",
        r"^Create ", r"^Show ", r"^Demonstrate ",
    ]
    for pattern in garbage_patterns:
        if re.search(pattern, stripped):
            return False

    title_only_pattern = r"^[\u4e00-\u9fffA-Za-z0-9\s\+\-\=\^\(\)\{\}\[\]]{2,15}$"
    if (
        re.match(title_only_pattern, stripped)
        and len(stripped) < 20
        and not any(m in stripped for m in ("我们", "大家", "可以看到", "首先"))
    ):
        return False

    spoken_markers = [
        "我们", "大家", "可以看到", "注意到", "这里", "现在",
        "首先", "然后", "接下来", "最后", "也就是说", "换句话说",
        "实际上", "让我们", "想象一下", "大家看", "注意看",
    ]
    spoken_count = sum(1 for marker in spoken_markers if marker in stripped)

    if spoken_count >= 2:
        return True
    if spoken_count >= 1 and len(stripped) > 25:
        return True
    if len(stripped) > 50:
        return True

    return False


def _build_template_narration(
    implemented_beats: list[str],
    beat_to_narration_map: list[str],
    user_topic: str,
) -> str:
    """Generate template-based narration from beat structure when LLM fails.

    Produces actual spoken-style Chinese text instead of raw user request text.
    This is the safe fallback that never returns garbage.
    """
    parts: list[str] = []

    topic = user_topic.strip().split("\uff0c")[0].split(",")[0][:30]
    if not topic or len(topic) < 2:
        topic = "这个内容"
    parts.append(f"大家好，今天我们来学习{topic}。")

    used_beats = beat_to_narration_map if beat_to_narration_map else implemented_beats
    total = len(used_beats)

    for i, entry in enumerate(used_beats):
        entry_stripped = entry.strip()
        if not entry_stripped:
            continue
        if total == 1:
            parts.append(f"{entry_stripped}")
        elif i == 0:
            parts.append(f"首先，{entry_stripped}。")
        elif i == total - 1:
            parts.append(f"最后，{entry_stripped}。")
        else:
            parts.append(f"接下来，{entry_stripped}。")

    parts.append("以上就是今天的内容，谢谢大家的观看。")

    return "".join(parts)


# ── Review Frame 标签 ─────────────────────────────────────────────


def _build_frame_labels(
    implemented_beats: list[str] | None,
    count: int,
) -> list[str]:
    """Generate beat-aligned labels for extracted review frames.

    Returns labels like ``["opening", "beat_1__Intro", ..., "ending"]``.
    """
    if count <= 0 or not implemented_beats:
        return [f"frame_{i + 1}" for i in range(count)]

    labels: list[str] = ["opening"]
    n_beats = len(implemented_beats)

    if count > 2:
        middle_slots = count - 2
        for i in range(middle_slots):
            beat_idx = min(i, n_beats - 1)
            beat_name = implemented_beats[beat_idx].replace(" ", "_")
            labels.append(f"beat_{beat_idx + 1}__{beat_name}")

    if count >= 2:
        last_beat = implemented_beats[-1].replace(" ", "_")
        labels.append(f"ending__{last_beat}")

    while len(labels) < count:
        labels.append(f"frame_{len(labels) + 1}")
    return labels[:count]


# ── Render Review ─────────────────────────────────────────────────


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
    implemented_beats: list[str] | None = None,
) -> RenderReviewOutput:
    """Ask Claude to review sampled render frames and return a structured verdict."""
    beat_labels = _build_frame_labels(implemented_beats, len(frame_paths))
    labeled_frames = "\n".join(
        f"- Frame {i + 1} [{label}]: {path}"
        for i, (path, label) in enumerate(zip(frame_paths, beat_labels))
    )
    measured_duration = (
        f"{actual_duration_seconds:.2f}s"
        if actual_duration_seconds is not None and actual_duration_seconds > 0
        else "unknown"
    )
    review_prompt = (
        "Use the `render-review` skill to review this rendered Manim video.\n"
        "Do not write, edit, or render anything in this pass. Only review the output.\n\n"

        "## MANDATORY: Visual Analysis of Each Frame\n"
        "You MUST use the Read tool to examine EVERY frame image file listed below.\n"
        "For each frame, provide a visual assessment covering:\n"
        "- What is visibly on screen (objects, text, formulas, labels, arrows)\n"
        "- Visual density (sparse / balanced / crowded)\n"
        "- Whether the focal point is clear and unambiguous\n"
        "- Label and formula readability (clear / partially obscured / illegible)\n"
        "- Any visual issues (overlap, cutoff, too small, wrong position, etc.)\n\n"

        f"Original user request:\n{user_text}\n\n"
        "Duration target:\n"
        f"- requested runtime: about {format_target_duration(target_duration_seconds)}\n"
        f"- measured render runtime: {measured_duration}\n\n"
        "Visible plan / build context:\n"
        f"{plan_text or '(no plan text available)'}\n\n"
        f"Rendered video path:\n- {video_output}\n\n"
        "Sampled review frames (MUST read each one):\n"
        f"{labeled_frames}\n"
    )

    review_options = _build_options(
        cwd=cwd,
        system_prompt=system_prompt,
        max_turns=16,
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


# ── 解说生成 Pass ─────────────────────────────────────────────────


async def generate_narration(
    *,
    user_text: str,
    target_duration_seconds: int,
    plan_text: str,
    po: PipelineOutput,
    video_output: str,
    cwd: str,
    system_prompt: str,
    quality: str,
    prompt_file: str | None,
    log_callback: Callable[[str], None] | None,
    dispatcher: _MessageDispatcher,
) -> str:
    """Run an independent no-tools LLM call to generate spoken Chinese narration.

    Returns the generated narration text. Falls back to template-based narration
    if the LLM call fails or returns garbage.
    """
    resolved_cwd = str(Path(cwd).resolve())

    existing = po.narration
    if existing and existing.strip() and _looks_like_spoken_narration(existing):
        dispatcher._print("  [NARRATION] Existing narration looks valid, skipping generation.")
        logger.info("generate_narration: existing narration passed validation, reusing")
        return existing.strip()

    if existing and existing.strip():
        dispatcher._print(
            f"  [NARRATION] Existing narration failed validation "
            f"(len={len(existing.strip())}). Regenerating."
        )

    dispatcher._print("  [NARRATION] Generating spoken narration via dedicated LLM pass...")

    narration_prompt = prompt_builder.build_narration_generation_prompt(
        user_text=user_text,
        target_duration_seconds=target_duration_seconds,
        plan_text=plan_text,
        implemented_beats=list(po.implemented_beats),
        beat_to_narration_map=list(po.beat_to_narration_map),
        build_summary=po.build_summary,
        video_duration_seconds=po.duration_seconds,
    )

    narration_options = _build_options(
        cwd=resolved_cwd,
        system_prompt=system_prompt,
        max_turns=3,
        prompt_file=prompt_file,
        quality=quality,
        log_callback=log_callback,
        allowed_tools=[],
        use_default_output_format=False,
    )

    prev_text_len = len(dispatcher.collected_text)

    generated_text: str | None = None
    try:
        async for message in query(prompt=narration_prompt, options=narration_options):
            dispatcher.dispatch(message)
    except Exception as exc:
        warning = f"Narration LLM generation failed: {exc}"
        dispatcher._print(f"  [WARN] {warning}")
        logger.warning("generate_narration: %s", warning)

    new_texts = dispatcher.collected_text[prev_text_len:]
    if new_texts:
        generated_text = "\n".join(new_texts).strip()

    if generated_text and _looks_like_spoken_narration(generated_text):
        final = generated_text
        dispatcher._print(f"  [NARRATION] Generated narration ({len(final)} chars): {final[:80]}...")
        return final

    dispatcher._print("  [NARRATION] LLM output failed validation, using template fallback.")
    topic_hint = user_text.strip().split("\uff0c")[0].split(",")[0][:30]
    template_text = _build_template_narration(
        implemented_beats=list(po.implemented_beats),
        beat_to_narration_map=list(po.beat_to_narration_map),
        user_topic=topic_hint,
    )
    dispatcher._print(f"  [NARRATION] Template narration ({len(template_text)} chars)")
    return template_text


# ── PO 元数据填充（消除重复）────────────────────────────────────


def _populate_po_metadata(
    po: PipelineOutput,
    dispatcher: _MessageDispatcher,
    result_summary: dict[str, Any] | None,
    target_duration_seconds: int,
    plan_text: str,
) -> None:
    """Fill standard metadata fields on PO from dispatcher + result summary."""
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


# ── 主 Pipeline ────────────────────────────────────────────────────


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
    intro_outro: bool = False,
    intro_outro_backend: str = "revideo",
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
        # ══════════════════════════════════════════════
        # Phase 1/5: Scene Planning Pass
        # ══════════════════════════════════════════════
        planning_result_summary: dict[str, Any] | None = None
        planning_prompt = _build_scene_plan_prompt(
            user_text,
            target_duration_seconds,
            resolved_cwd,
        )
        async for message in query(prompt=planning_prompt, options=planning_options):
            dispatcher.dispatch(message)
        planning_result_summary = dispatcher.result_summary

        if not has_visible_scene_plan(dispatcher.collected_text):
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

        if not has_scene_plan_skill_signature(dispatcher.collected_text):
            dispatcher._print("")
            dispatcher._print(
                "  [WARN] Visible plan does not include the optional scene-plan signature."
            )
            dispatcher._print(
                "  Continuing because the visible plan itself is present."
            )

        plan_text = extract_visible_scene_plan_text(dispatcher.collected_text)
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

        # ══════════════════════════════════════════════
        # Phase 2/5: Implementation Pass
        # ══════════════════════════════════════════════
        user_prompt = _build_implementation_prompt(
            user_text,
            target_duration_seconds,
            plan_text,
            resolved_cwd,
        )
        async for message in query(prompt=user_prompt, options=build_options):
            dispatcher.dispatch(message)
            if dispatcher.implementation_started:
                if not has_visible_scene_plan(dispatcher.collected_text):
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

        result_summary = merge_result_summaries(
            planning_result_summary,
            dispatcher.result_summary,
        )
        if result_summary is not None:
            dispatcher.partial_run_turns = result_summary.get("turns")
            dispatcher.partial_run_duration_ms = result_summary.get("duration_ms")
            dispatcher.partial_run_cost_usd = result_summary.get("cost_usd")
        dispatcher.partial_run_tool_use_count = dispatcher.tool_use_count
        dispatcher.partial_run_tool_stats = dict(dispatcher.tool_stats)

        # ══════════════════════════════════════════════
        # Phase 3/5: Resolve Render Output
        # ══════════════════════════════════════════════
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
            _populate_po_metadata(po, dispatcher, result_summary, target_duration_seconds, plan_text)

        needs_build_summary = not has_structured_build_summary(po)
        needs_narration_summary = not has_narration_sync_summary(po)
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
            result_summary = merge_result_summaries(result_summary, repair_result_summary)
            po = dispatcher.get_pipeline_output()
            if po is not None:
                _populate_po_metadata(po, dispatcher, result_summary, target_duration_seconds, plan_text)

        if not has_structured_build_summary(po):
            warning = (
                "Claude skipped the scene-build summary. "
                "Continuing with partial structured output because a render exists."
            )
            dispatcher._print(f"  [WARN] {warning}")
            logger.warning("run_pipeline: %s", warning)

        if not has_narration_sync_summary(po):
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

        # ══════════════════════════════════════════════
        # Render Review + Duration Check
        # ══════════════════════════════════════════════
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
            implemented_beats=po.implemented_beats if po else None,
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
                implemented_beats=po.implemented_beats if po else None,
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
                po.review_frame_analyses = [
                    fa.model_dump() for fa in (review_result.frame_analyses or [])
                ]
                po.review_vision_analysis_used = review_result.vision_analysis_used
            dispatcher.partial_review_summary = review_result.summary
            dispatcher.partial_review_approved = review_result.approved
            dispatcher.partial_review_blocking_issues = list(review_result.blocking_issues)
            dispatcher.partial_review_suggested_edits = list(review_result.suggested_edits)
            dispatcher.partial_review_frame_paths = list(review_frames)
            dispatcher.partial_review_frame_analyses = [
                fa.model_dump() for fa in (review_result.frame_analyses or [])
            ]
            dispatcher.partial_review_vision_analysis_used = review_result.vision_analysis_used
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

        duration_issue = duration_target_issue(
            po.duration_seconds if po is not None else None,
            target_duration_seconds,
            formatter=format_target_duration,
        )
        if duration_issue is not None:
            dispatcher._print(f"  [WARN] {duration_issue}")
            logger.warning("run_pipeline: duration target miss: %s", duration_issue)
        if duration_issue is None and po is not None and po.duration_seconds is not None:
            dispatcher._print(
                "  [REVIEW] Duration check passed: "
                f"{po.duration_seconds:.1f}s vs target {target_duration_seconds}s"
            )

        # ══════════════════════════════════════════════
        # Phase 3.5/5: Narration Generation Pass
        # ══════════════════════════════════════════════
        dispatcher._print(f"  {_EMOJI['gear']} Phase 3.5/5: narration generation")
        _emit_status(
            event_callback,
            task_status="running",
            phase="narration",
            message="Generating spoken narration for TTS",
        )
        narration_text = await generate_narration(
            user_text=user_text,
            target_duration_seconds=target_duration_seconds,
            plan_text=plan_text,
            po=po,
            video_output=video_output,
            cwd=resolved_cwd,
            system_prompt=system_prompt,
            quality=quality,
            prompt_file=prompt_file,
            log_callback=_counting_log_callback,
            dispatcher=dispatcher,
        )
        if po is not None:
            po.narration = narration_text

        # Merge narration-phase stats
        narration_result_summary = dispatcher.result_summary
        result_summary = merge_result_summaries(result_summary, narration_result_summary)
        if po is not None and result_summary is not None:
            po.run_turns = result_summary.get("turns")
            po.run_duration_ms = result_summary.get("duration_ms")
            po.run_cost_usd = result_summary.get("cost_usd")

        # ══════════════════════════════════════════════
        # Phase 4+5/5: TTS Synthesis + Video Mux
        # ══════════════════════════════════════════════
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
        if narration_is_too_short_for_video(
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

        # BGM generation
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

        # Final mux
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

        # --- Phase 5b: Optional intro/outro concat ---
        if intro_outro and po is not None:
            concat_parts: list[str | None] = []

            if po.intro_video_path and Path(po.intro_video_path).exists():
                concat_parts.append(po.intro_video_path)

            concat_parts.append(final_video)  # Main video always present

            if po.outro_video_path and Path(po.outro_video_path).exists():
                concat_parts.append(po.outro_video_path)

            if len(concat_parts) > 1:
                dispatcher._print("[MUX] Phase 5b: concatenating intro/outro segments")
                _emit_status(
                    event_callback,
                    task_status="running",
                    phase="concat",
                    message="Concatenating intro/outro segments",
                )
                final_video = await video_builder.concat_videos(
                    video_paths=cast("list[str]", concat_parts),
                    output_path=output_path,
                )
                if po is not None:
                    po.final_video_output = final_video
                dispatcher._print(f"[MUX] Concatenated video: {final_video}")

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
