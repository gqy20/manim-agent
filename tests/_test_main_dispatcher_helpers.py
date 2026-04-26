"""Shared helpers for split dispatcher-related test modules."""

from __future__ import annotations

from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    TaskNotificationMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
)

from manim_agent import pipeline as main_module
from manim_agent.dispatcher import _MessageDispatcher

__all__ = [
    "TaskNotificationMessage",
    "_MessageDispatcher",
    "_make_assistant_message",
    "_make_result_message",
    "_make_text_block",
    "_make_thinking_block",
    "_make_tool_result_block",
    "_make_tool_use_block",
    "_make_two_stage_query_side_effect",
    "_phase2_output",
    "_DEFAULT_DRAFT_SOURCE",
    "main_module",
]


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


def _phase2_output(**overrides):
    data = {
        "video_output": "out.mp4",
        "implemented_beats": ["Hook", "Main idea", "Wrap-up"],
        "build_summary": "Built the planned teaching beats.",
        "deviations_from_plan": [],
        "narration": "First show a circle, then morph it into a square.",
        "beat_to_narration_map": [
            "Introduce the intuition with a visual hook.",
            "Explain the core relationship clearly.",
            "Restate the final takeaway.",
        ],
        "narration_coverage_complete": True,
        "estimated_narration_duration_seconds": 12.0,
    }
    data.update(overrides)
    return data


_DEFAULT_DRAFT_SOURCE = """
from manim import *

class GeneratedScene(Scene):
    def construct(self):
        self.beat_001_hook()
        self.beat_002_main_idea()
        self.beat_003_wrap_up()

    def beat_001_hook(self):
        self.play(FadeIn(Square()), run_time=10)
        self.wait(1)

    def beat_002_main_idea(self):
        self.play(FadeIn(Circle()), run_time=35)
        self.wait(1)

    def beat_003_wrap_up(self):
        self.play(FadeIn(Triangle()), run_time=15)
        self.wait(1)
"""


def _make_script_draft_messages(cwd: str | None = None):
    if cwd:
        scene_path = Path(cwd) / "scene.py"
        if not scene_path.exists():
            scene_path.write_text(_DEFAULT_DRAFT_SOURCE, encoding="utf-8")
    return [
        _make_result_message(
            num_turns=1,
            result="script draft complete",
            structured_output={
                "scene_file": "scene.py",
                "scene_class": "GeneratedScene",
                "implemented_beats": ["Hook", "Main idea", "Wrap-up"],
                "build_summary": "Drafted the beat-first scene script.",
                "beat_timing_seconds": {
                    "beat_001_hook": 11.0,
                    "beat_002_main_idea": 36.0,
                    "beat_003_wrap_up": 16.0,
                },
                "estimated_duration_seconds": 63.0,
                "deviations_from_plan": [],
                "source_code": _DEFAULT_DRAFT_SOURCE,
            },
        ),
    ]


def _make_two_stage_query_side_effect(build_messages):
    """Return planning, then default Phase 2A draft, then caller's Phase 2B messages."""
    planning_messages = [
        _make_result_message(
            num_turns=1,
            result="planning complete",
            structured_output={
                "build_spec": {
                    "mode": "teaching-animation",
                    "learning_goal": "Explain the core idea clearly.",
                    "audience": "Beginner learners.",
                    "target_duration_seconds": 60,
                    "beats": [
                        {
                            "id": "beat_001_hook",
                            "title": "Hook",
                            "visual_goal": "Open with a simple visual hook.",
                            "narration_intent": "Introduce the intuition.",
                            "target_duration_seconds": 10,
                            "required_elements": ["title", "simple shape"],
                            "segment_required": True,
                        },
                        {
                            "id": "beat_002_main_idea",
                            "title": "Main idea",
                            "visual_goal": "Show the main relationship clearly.",
                            "narration_intent": "Explain the core relationship.",
                            "target_duration_seconds": 35,
                            "required_elements": ["labels", "arrows"],
                            "segment_required": True,
                        },
                        {
                            "id": "beat_003_wrap_up",
                            "title": "Wrap-up",
                            "visual_goal": "Summarize the takeaway visually.",
                            "narration_intent": "Restate the final takeaway.",
                            "target_duration_seconds": 15,
                            "required_elements": ["summary text"],
                            "segment_required": True,
                        },
                    ],
                },
            },
        ),
    ]
    call_count = {"value": 0}

    async def _side_effect(*_args, **_kwargs):
        call_count["value"] += 1
        options = _kwargs.get("options")
        if call_count["value"] == 1:
            messages = planning_messages
        elif call_count["value"] == 2:
            messages = _make_script_draft_messages(getattr(options, "cwd", None))
        else:
            cwd = getattr(options, "cwd", None)
            if cwd:
                output = Path(cwd) / "out.mp4"
                if not output.exists():
                    output.write_bytes(b"render")
            messages = build_messages
        for message in messages:
            yield message

    return _side_effect
