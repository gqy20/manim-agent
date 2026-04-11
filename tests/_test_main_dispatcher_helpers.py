"""Shared helpers for split dispatcher-related test modules."""

import json
from pathlib import Path
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from manim_agent import __main__ as main_module
from manim_agent.__main__ import _MessageDispatcher
from manim_agent.hooks import create_hook_state
from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    RateLimitEvent,
    RateLimitInfo,
    TaskProgressMessage,
    TaskNotificationMessage,
    TaskUsage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
    ThinkingBlock,
)


def _make_text_block(text: str) -> TextBlock:
    return TextBlock(text=text)


def _make_tool_use_block(name: str, input_dict: dict | None = None, tool_id: str = "tu_001") -> ToolUseBlock:
    return ToolUseBlock(id=tool_id, name=name, input=input_dict or {})


def _make_tool_result_block(tool_id: str = "tu_001", content: str = "ok", is_error: bool = False) -> ToolResultBlock:
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
