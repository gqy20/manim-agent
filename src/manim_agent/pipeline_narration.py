"""Narration generation: quality checks, template fallback, and generation pass."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from pathlib import Path

from claude_agent_sdk import ResultMessage, query

from .dispatcher import _MessageDispatcher
from .schemas import Phase3_5NarrationOutput, PhaseSchemaRegistry
from .pipeline_config import build_options
from .prompt_builder import build_narration_generation_prompt

logger = logging.getLogger(__name__)


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
        r"请制作",
        r"请帮我",
        r"生成一段",
        r"创建一个",
        r"用动画演示",
        r"可视化",
        r"^Create ",
        r"^Show ",
        r"^Demonstrate ",
    ]
    for pattern in garbage_patterns:
        if re.search(pattern, stripped):
            return False

    title_only_pattern = r"^[一-鿿A-Za-z0-9\s\+\-\=\^\(\)\{\}\[\]]{2,15}$"
    if (
        re.match(title_only_pattern, stripped)
        and len(stripped) < 20
        and not any(m in stripped for m in ("我们", "大家", "可以看到", "首先"))
    ):
        return False

    spoken_markers = [
        "我们",
        "大家",
        "可以看到",
        "注意到",
        "这里",
        "现在",
        "首先",
        "然后",
        "接下来",
        "最后",
        "也就是说",
        "换句话说",
        "实际上",
        "让我们",
        "想象一下",
        "大家看",
        "注意看",
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
) -> Phase3_5NarrationOutput:
    """Generate template-based narration from beat structure when LLM fails.

    Produces actual spoken-style Chinese text instead of raw user request text.
    This is the safe fallback that never returns garbage.
    """
    parts: list[str] = []

    topic = user_topic.strip().split("，")[0].split(",")[0][:30]
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

    text = "".join(parts)
    return Phase3_5NarrationOutput(
        narration=text,
        beat_coverage=list(used_beats) if used_beats else (list(implemented_beats) if implemented_beats else ["默认内容"]),
        char_count=len(text),
        generation_method="template",
    )


async def generate_narration(
    *,
    user_text: str,
    target_duration_seconds: int,
    plan_text: str,
    po: Any,
    video_output: str,
    cwd: str,
    system_prompt: str,
    quality: str,
    prompt_file: str | None = None,
    log_callback: Callable[[str], None] | None = None,
    dispatcher: _MessageDispatcher,
) -> Phase3_5NarrationOutput:
    """Run an independent LLM call to generate spoken Chinese narration.

    Returns structured narration output. Falls back to template-based narration
    if the LLM call fails or returns garbage.
    """
    resolved_cwd = str(Path(cwd).resolve())

    existing = getattr(po, "narration", None)
    if existing and existing.strip() and _looks_like_spoken_narration(existing):
        dispatcher._print("  [NARRATION] Existing narration looks valid, skipping generation.")
        logger.info("generate_narration: existing narration passed validation, reusing")
        return Phase3_5NarrationOutput(
            narration=existing.strip(),
            beat_coverage=list(po.implemented_beats) if hasattr(po, "implemented_beats") else [],
            char_count=len(existing.strip()),
            generation_method="reused",
        )

    if existing and existing.strip():
        dispatcher._print(
            f"  [NARRATION] Existing narration failed validation "
            f"(len={len(existing.strip())}). Regenerating."
        )

    dispatcher._print("  [NARRATION] Generating spoken narration via dedicated LLM pass...")

    narration_prompt = build_narration_generation_prompt(
        user_text=user_text,
        target_duration_seconds=target_duration_seconds,
        plan_text=plan_text,
        implemented_beats=list(po.implemented_beats) if hasattr(po, "implemented_beats") else [],
        beat_to_narration_map=list(po.beat_to_narration_map) if hasattr(po, "beat_to_narration_map") else [],
        build_summary=po.build_summary if hasattr(po, "build_summary") else "",
        video_duration_seconds=po.duration_seconds if hasattr(po, "duration_seconds") else None,
    )

    narration_opts = build_options(
        cwd=resolved_cwd,
        system_prompt=system_prompt,
        max_turns=3,
        prompt_file=prompt_file,
        quality=quality,
        log_callback=log_callback,
        allowed_tools=[],
        use_default_output_format=False,
        output_format=PhaseSchemaRegistry.output_format_schema("phase3_5_narration"),
    )

    generated_text: str | None = None
    try:
        result_message: ResultMessage | None = None
        async for message in query(prompt=narration_prompt, options=narration_opts):
            dispatcher.dispatch(message)
            if isinstance(message, ResultMessage):
                result_message = message

        if result_message is not None and result_message.structured_output is not None:
            raw = result_message.structured_output
            if isinstance(raw, str):
                raw = json.loads(raw)
            try:
                validated = Phase3_5NarrationOutput.model_validate(raw)
                dispatcher._print(
                    f"  [NARRATION] Structured narration accepted ({len(validated.narration)} chars)"
                )
                return validated
            except Exception as exc:
                logger.warning("generate_narration: structured output validation failed: %s", exc)
                # Fall through to collected_text extraction below
    except Exception as exc:
        warning = f"Narration LLM generation failed: {exc}"
        dispatcher._print(f"  [WARN] {warning}")
        logger.warning("generate_narration: %s", warning)

    # Fallback: extract from collected_text (backward-compatible path for non-SDK environments)
    new_texts = dispatcher.collected_text
    if new_texts:
        generated_text = "\n".join(new_texts).strip()

    if generated_text and _looks_like_spoken_narration(generated_text):
        dispatcher._print(
            f"  [NARRATION] Generated narration ({len(generated_text)} chars): {generated_text[:80]}..."
        )
        return Phase3_5NarrationOutput(
            narration=generated_text,
            beat_coverage=list(po.implemented_beats) if hasattr(po, "implemented_beats") else [],
            char_count=len(generated_text),
            generation_method="llm",
        )

    # Template fallback
    dispatcher._print("  [NARRATION] LLM output failed validation, using template fallback.")
    topic_hint = user_text.strip().split("，")[0].split(",")[0][:30]
    template_output = _build_template_narration(
        implemented_beats=list(po.implemented_beats) if hasattr(po, "implemented_beats") else [],
        beat_to_narration_map=list(po.beat_to_narration_map) if hasattr(po, "beat_to_narration_map") else [],
        user_topic=topic_hint,
    )
    dispatcher._print(f"  [NARRATION] Template narration ({len(template_output.narration)} chars)")
    return template_output
