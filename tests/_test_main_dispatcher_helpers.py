"""Shared helpers for split dispatcher-related test modules."""

from __future__ import annotations

import json

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    TaskNotificationMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
)

from manim_agent.dispatcher import _MessageDispatcher
from manim_agent import pipeline as main_module


def _make_text_block(text: str) -> TextBlock:
    return TextBlock(text=text)


def _make_tool_use_block(
    name: str,
    input_dict: dict | None = None,
    tool_id: str = "tu_001",
) -> ToolUseBlock:
    return ToolUseBlock(id=tool_id, name=name, input=input_dict or {})


def _make_tool_result_block(
    tool_id: str = "tu_001",
    content: str = "ok",
    is_error: bool = False,
) -> ToolResultBlock:
    return ToolResultBlock(tool_use_id=tool_id, content=content, is_error=is_error)


def _make_thinking_block(thought: str = "let me think...") -> ThinkingBlock:
    return ThinkingBlock(thinking=thought, signature="sig")


def _make_assistant_message(*blocks) -> AssistantMessage:
    return AssistantMessage(content=list(blocks), model="claude-sonnet-4-20250514")


def _make_result_message(**overrides) -> ResultMessage:
    defaults = dict(
        subtype="result",
        duration_ms=5000,
        duration_api_ms=4500,
        is_error=False,
        num_turns=3,
        session_id="sess-abc",
        stop_reason="end_turn",
        total_cost_usd=0.0123,
        usage={"input_tokens": 1000, "output_tokens": 2000},
    )
    defaults.update(overrides)
    return ResultMessage(**defaults)


def _make_scene_plan_text() -> str:
    return """Mode
Teaching animation
Learning Goal
Explain the core idea clearly.
Audience
Beginner learners.
Beat List
1. Hook
2. Main idea
3. Wrap-up
Narration Outline
Open with intuition, then explain the main relationship.
Visual Risks
Avoid overcrowding labels.
Build Handoff
Implement the beats in order and keep narration aligned.
"""


def _make_two_stage_query_side_effect(build_messages):
    planning_messages = [
        _make_assistant_message(_make_text_block(_make_scene_plan_text())),
        _make_result_message(num_turns=1, result="planning complete"),
    ]
    call_count = {"value": 0}

    async def _side_effect(*_args, **_kwargs):
        call_count["value"] += 1
        messages = planning_messages if call_count["value"] == 1 else build_messages
        for message in messages:
            yield message

    return _side_effect
