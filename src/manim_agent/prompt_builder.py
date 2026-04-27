"""Prompt building helpers for the staged Manim pipeline."""

from __future__ import annotations

import json


def format_target_duration(seconds: int) -> str:
    """Format a target runtime for prompt guidance."""
    if seconds < 60:
        return f"{seconds} seconds"
    minutes, remainder = divmod(seconds, 60)
    if remainder == 0:
        return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"
    return f"{minutes}m {remainder}s"


def build_user_prompt(
    user_text: str,
    target_duration_seconds: int,
    *,
    include_intro_outro: bool = False,
) -> str:
    """Build execution guidance for a single agent pass."""
    normalized = user_text.strip()
    target_duration = format_target_duration(target_duration_seconds)
    guidance = (
        "\n\n执行要求：\n"
        f"- 目标最终视频时长：约 {target_duration}。\n"
        "- 设计 beat 数量、节奏和解说密度，使其接近目标运行时长。\n"
        "- 30 秒和 1 分钟的短视频偏好简短聚焦的讲解，3 分钟和 5 分钟的视频可以做更完整的演示。\n"
        "- 使用运行时注入的 `manim-production` 插件。\n"
        "- 插件位置是只读运行时引用，不是可写任务目录。\n"
        "- 不要用 Bash、Read、ls、find 或路径探测来验证插件是否存在。\n"
        "- 通过注入的插件工作流直接使用 `scene-plan`、`scene-build`、`scene-direction`、`layout-safety`、`narration-sync` 和 `render-review` skills。\n"
        "- 将 `layout-safety` 视为密集 beat 的建议性审计，而非盲目自动失败规则。\n"
        "- 实现前使用已批准的构建计划/上下文，保持规划的 beat 顺序，除非调试需要极小修复。\n"
        "- 在构建计划/上下文就绪之前不要开始编写 `scene.py`。\n"
        "- 在 structured_output 中包含 `implemented_beats`，即实际构建的有序 beat 标题列表。\n"
        "- 在 structured_output 中包含 `build_summary`，即构建阶段实现的简要摘要。\n"
        "- 在 structured_output 中包含 `deviations_from_plan`，即使为空也要作为数组返回。\n"
        "- structured_output 聚焦于 Agent 必须编写的事实；pipeline 可从已批准的 build spec 推导 beat 级别的解说记录。\n"
        "- 所有文件仅保存在任务目录内。\n"
        "- 主脚本写入 scene.py，除非确实需要多个文件。\n"
        "- 使用 GeneratedScene 作为主 Manim Scene 类名，除非用户明确要求其他名称。\n"
        "- 从任务目录直接运行 Manim：`manim ... scene.py GeneratedScene`。\n"
        "- 不要使用绝对仓库路径，不要 cd 到仓库根目录，不要直接调用 `.venv/Scripts/python`。\n"
        "- 以自然简体中文返回 structured_output.narration，除非用户明确要求其他语言。\n"
        "- 解说应为口语化并与动画同步，覆盖完整流程而不是压缩成一句话总结。\n"
    )
    if include_intro_outro:
        guidance += (
            "\n- 使用 `intro-outro` skill 来设计品牌化的片头和/或片尾片段。\n"
            "- 如果内容合适，在 structured_output 中输出 `intro_spec` 和/或 `outro_spec`。\n"
            "- 如果生成了片头或片尾视频文件，将其路径报告为 `intro_video_path` 和 `outro_video_path`。\n"
            "- 片头和片尾片段各控制在 3–5 秒之间。\n"
        )
    return f"{normalized}{guidance}" if normalized else guidance.strip()


def build_implementation_prompt(
    user_text: str,
    target_duration_seconds: int,
    plan_text: str,
    *,
    include_intro_outro: bool = False,
) -> str:
    """Build the implementation prompt after a planning pass has been accepted."""
    normalized = user_text.strip()
    target_duration = format_target_duration(target_duration_seconds)
    guidance = (
        "\n\n实现阶段：\n"
        f"- 目标最终视频时长：约 {target_duration}。\n"
        "- 以下构建计划/上下文已获批准。基于它进行实现，而不是创建新计划。\n"
        "- 继续使用运行时注入的 `manim-production` 插件。\n"
        "- 通过注入的插件工作流使用 `scene-build`、`scene-direction`、`layout-safety`、`narration-sync` 和 `render-review`。\n"
        "- 将 `layout-safety` 视为密集 beat 的建议性审计，并用视觉判断解读警告。\n"
        "- 插件位置是只读运行时引用，不是可写任务目录。\n"
        "- 实现期间不要用 shell 或文件系统探测来验证插件文件。\n"
        "- 保持规划的 beat 顺序，除非调试需要极小修复。\n"
        "- 不要从全新的规划阶段开始；从已批准的计划开始实现。\n"
        "- 在 structured_output 中包含 `implemented_beats`，即实际构建的有序 beat 标题列表。\n"
        "- 在 structured_output 中包含 `build_summary`，即构建阶段实现的简要摘要。\n"
        "- 在 structured_output 中包含 `deviations_from_plan`，即使为空也要作为数组返回。\n"
        "- structured_output 聚焦于 Agent 必须编写的事实；pipeline 可从已批准的 build spec 推导 beat 级别的解说记录。\n"
        "- 所有文件仅保存在任务目录内。\n"
        "- 主脚本写入 scene.py，除非确实需要多个文件。\n"
        "- 使用 GeneratedScene 作为主 Manim Scene 类名，除非用户明确要求其他名称。\n"
        "- 从任务目录直接运行 Manim：`manim ... scene.py GeneratedScene`。\n"
        "- 不要使用绝对仓库路径，不要 cd 到仓库根目录，不要直接调用 `.venv/Scripts/python`。\n"
        "- 以自然简体中文返回 structured_output.narration，除非用户明确要求其他语言。\n"
        "- 解说应为口语化并与动画同步，覆盖完整流程而不是压缩成一句话总结。\n"
    )
    if include_intro_outro:
        guidance += (
            "- 如果已批准的计划包含片头/片尾规划部分，"
            "使用 `intro-outro` skill 来实现这些片段。\n"
            "- 如果适用，在 structured_output 中输出 `intro_spec`/`outro_spec` 和 `intro_video_path`/`outro_video_path`。\n"
            "- 使用 Manim 回退方案（TitleCard/EndingCard）或 Revideo 来渲染片头/片尾场景。\n"
        )
    guidance += (
        "\nApproved build plan/context:\n"
        f"{plan_text}\n"
    )
    return f"{normalized}{guidance}" if normalized else guidance.strip()


def build_output_repair_prompt(
    user_text: str,
    target_duration_seconds: int,
    *,
    plan_text: str,
    partial_output: dict[str, object] | None,
    raw_result_text: str | None = None,
    video_output: str | None,
    segment_video_paths: list[str] | None = None,
    artifact_inventory: list[str] | None = None,
    validation_issue: str | None = None,
    render_mode: str = "full",
) -> str:
    """Build a no-tools repair prompt for missing structured output fields."""
    normalized = user_text.strip()
    target_duration = format_target_duration(target_duration_seconds)
    render_mode = render_mode.strip().lower() or "full"
    segment_video_paths = [path for path in (segment_video_paths or []) if path]
    partial_output_json = json.dumps(
        partial_output or {},
        ensure_ascii=False,
        indent=2,
    )
    artifact_inventory = [item for item in (artifact_inventory or []) if item]
    render_artifact_guidance = (
        f"- 保持 `video_output` 设为 `{video_output}`。\n"
        "- 完全保留现有的渲染产物路径。\n"
    )
    if render_mode == "segments" and not video_output:
        render_artifact_guidance = (
            "- 保持 `video_output` 为 null。不要编造合成的全长度渲染路径。\n"
            "- 保持 `segment_video_paths` 为有序的 beat 级别交付物。\n"
        )
        if segment_video_paths:
            segment_paths_json = json.dumps(segment_video_paths, ensure_ascii=False, indent=2)
            render_artifact_guidance += (
                "- 保持 `segment_video_paths` 与以下现有文件完全对齐：\n"
                f"{segment_paths_json}\n"
            )
    guidance = (
        "\n\n结构化输出修复阶段：\n"
        f"- 目标最终视频时长：约 {target_duration}。\n"
        "- 本阶段不使用任何工具。\n"
        "- 不要编写、编辑、渲染、探测或检查文件。\n"
        "- 渲染/构建已经完成。不要继续构建。\n"
        "- 你的唯一任务是返回修正后的 structured_output 对象。\n"
        "- 仅使用已批准的构建计划/上下文、部分 structured output、原始完成文本和提供的产物清单。\n"
        "- 不要编造所提供证据不支持的内容。\n"
        f"- `render_mode` 保持为 `{render_mode}`。\n"
        f"{render_artifact_guidance}"
        "- 仅填写需要从已批准计划和已完成工作中获取 Agent 知识的缺失实现事实。\n"
        "- `implemented_beats` 必须是实际实现的有序 beat 标题列表。\n"
        "- `build_summary` 必须简要总结动画构建完成了什么。\n"
        "- `deviations_from_plan` 必须是数组，即使为空。\n"
        "- 不要将 `implemented_beats` 留空。\n"
        "- 不要省略 `build_summary`。\n"
        "- pipeline 可在需要时从已批准的 build spec 推导 beat 到解说的对应关系、解说覆盖率和估计解说时长。\n"
        "- 如果未捕获源代码，将 `source_code` 保留为 null 而不是编造它。\n"
        "- 如果音频/字幕产物尚不存在，保持它们为 null。\n"
        "- 仅通过 schema 返回修正后的 structured output。\n"
    )
    if validation_issue:
        guidance += f"- Repair target: {validation_issue}\n"
    if raw_result_text:
        guidance += (
            "\nRaw final completion text from the prior pass:\n"
            f"{raw_result_text}\n"
        )
    if artifact_inventory:
        guidance += (
            "\nKnown artifacts already present:\n"
            f"{json.dumps(artifact_inventory, ensure_ascii=False, indent=2)}\n"
        )
    guidance += (
        "\nApproved build plan/context:\n"
        f"{plan_text}\n"
        "\nCurrent partial structured output:\n"
        f"{partial_output_json}\n"
    )
    return f"{normalized}{guidance}" if normalized else guidance.strip()


def build_narration_generation_prompt(
    user_text: str,
    target_duration_seconds: int,
    *,
    plan_text: str,
    implemented_beats: list[str],
    beat_to_narration_map: list[str],
    build_summary: str | None,
    video_duration_seconds: float | None,
    beat_timing: list[dict] | None = None,
) -> str:
    """Build a no-tools prompt for generating natural spoken Chinese narration.

    Runs after the render is complete, so the LLM has full context about
    what was actually built vs what was planned.
    """
    normalized = user_text.strip()
    target_duration = format_target_duration(target_duration_seconds)

    beats_json = json.dumps(implemented_beats, ensure_ascii=False, indent=2)
    beat_map_json = json.dumps(beat_to_narration_map, ensure_ascii=False, indent=2)
    beat_timing_json = json.dumps(beat_timing or [], ensure_ascii=False, indent=2)

    duration_context = (
        f"{video_duration_seconds:.1f}s"
        if video_duration_seconds is not None and video_duration_seconds > 0
        else "unknown"
    )

    # Character count targets based on video duration
    effective_duration = video_duration_seconds or target_duration_seconds
    char_min = max(20, int(effective_duration * 2.5))
    char_max = max(40, int(effective_duration * 4))

    guidance = (
        "\n\n解说生成阶段：\n"
        "- 本阶段不使用任何工具。\n"
        "- 不要编写、编辑、渲染、探测或检查文件。\n"
        "- 你的唯一任务是为已完成的教育数学动画生成自然口语化的简体中文解说。\n\n"

        "## 你要解说的内容\n"
        f"- 原始用户请求：{normalized}\n"
        f"- 目标视频时长：约 {target_duration}\n"
        f"- 实际渲染视频时长：{duration_context}\n\n"

        "## 动画结构（实际构建的内容）\n"
        f"- 已实现的 beats（按顺序）：\n{beats_json}\n\n"
        f"- 构建阶段的 beat 到解说提示：\n{beat_map_json}\n\n"
        f"- beat 时序窗口（存在时以它为准）：\n{beat_timing_json}\n\n"
        f"- 构建摘要：{build_summary or '(无)'}\n\n"

        "## 已批准的场景计划（上下文参考）\n"
        f"{plan_text}\n\n"

        "## 输出要求\n"
        "- 将解说写成连续的口语化中文，就像老师在给学生讲解一样。\n"
        "- 每句话应自然对应一个动画 beat，按顺序排列。\n"
        "- 同时返回 `beat_narrations`：每个 beat 时序窗口一条记录，使用相同的 "
        "`beat_id`、`title` 和 `target_duration_seconds` 值。\n"
        "- 每条 beat 解说保持简短，适配其目标时长。\n"
        "- 使用口语化连接词：'首先'、'接下来'、'然后'、"
        "'我们可以看到'、'注意'、'最后'、'也就是说'。\n"
        "- 避免使用项目符号、编号列表或指令性语言。\n"
        "- 不要包含用户请求文本、仅主题标题或元指令。\n"
        "- 不要说'请制作'、'演示'、'生成'等任务描述性措辞。\n"
        "- 不要逐字朗读公式——描述它们展示的内容即可。\n"
        f"- 将解说长度与视频时长匹配：目标约 "
        f"{char_min}–{char_max} 个中文字符。\n"
        "- 返回结构化的 `phase3_5_narration` 输出，包括完整的 "
        "`narration` 字符串和有序的 `beat_narrations` 列表。\n"
    )
    return f"{normalized}{guidance}" if normalized else guidance.strip()
