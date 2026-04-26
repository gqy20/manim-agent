"""Tests for TOOL_START/RESULT 配对逻辑（P1）。

覆盖：自动配对 name、duration_ms 计算、
未配对的 TOOL_RESULT 容错、并发安全。
"""

from __future__ import annotations

import time

import pytest

from claude_agent_sdk import ToolResultBlock, ToolUseBlock

from manim_agent.pipeline_events import EventType, PipelineEvent, ToolResultPayload
from manim_agent.dispatcher import _MessageDispatcher
from ._test_main_dispatcher_helpers import _make_assistant_message


class TestToolPairing:
    """TOOL_START 和 TOOL_RESULT 通过 tool_use_id 自动配对。"""

    def test_result_inherits_name_from_start(self):
        """TOOL_RESULT 的 name 字段应从配对的 TOOL_START 获取。"""
        events: list = []
        d = _MessageDispatcher(verbose=False)
        d.event_callback = events.append

        d.dispatch(_make_assistant_message(
            ToolUseBlock(id="tu_a", name="Bash", input={"command": "echo hi"})
        ))
        d.dispatch(_make_assistant_message(
            ToolResultBlock(tool_use_id="tu_a", content="hi\n", is_error=False)
        ))

        starts = [e for e in events if e.event_type == EventType.TOOL_START]
        results = [e for e in events if e.event_type == EventType.TOOL_RESULT]
        assert len(starts) == 1
        assert len(results) == 1
        assert results[0].data.name == "Bash"  # 从 start 配对获取

    def test_result_has_duration_ms(self):
        """配对后 TOOL_RESULT 应包含 duration_ms。"""
        events: list = []
        d = _MessageDispatcher(verbose=False)
        d.event_callback = events.append

        d.dispatch(_make_assistant_message(
            ToolUseBlock(id="tu_b", name="Write", input={"file_path": "x.py"})
        ))
        # 模拟短暂延迟确保 duration > 0
        import time as _t
        _t.sleep(0.01)
        d.dispatch(_make_assistant_message(
            ToolResultBlock(tool_use_id="tu_b", content=None, is_error=False)
        ))

        results = [e for e in events if e.event_type == EventType.TOOL_RESULT]
        assert len(results) == 1
        assert results[0].data.duration_ms is not None
        assert results[0].data.duration_ms >= 0

    def test_cross_pairing_by_tool_use_id(self):
        """多个工具交替调用时，配对应按 tool_use_id 精确匹配。"""
        events: list = []
        d = _MessageDispatcher(verbose=False)
        d.event_callback = events.append

        # A start → B start → A result → B result（交叉顺序）
        d.dispatch(_make_assistant_message(
            ToolUseBlock(id="tu_1", name="Read", input={"file_path": "a.txt"})
        ))
        d.dispatch(_make_assistant_message(
            ToolUseBlock(id="tu_2", name="Bash", input={"command": "ls"})
        ))
        d.dispatch(_make_assistant_message(
            ToolResultBlock(tool_use_id="tu_2", content="a.txt\n", is_error=False)
        ))
        d.dispatch(_make_assistant_message(
            ToolResultBlock(tool_use_id="tu_1", content="file contents", is_error=False)
        ))

        results = [e for e in events if e.event_type == EventType.TOOL_RESULT]
        assert len(results) == 2
        # tu_2 (Bash) 的结果先到
        assert results[0].data.tool_use_id == "tu_2"
        assert results[0].data.name == "Bash"
        # tu_1 (Read) 的结果后到
        assert results[1].data.tool_use_id == "tu_1"
        assert results[1].data.name == "Read"

    def test_unpaired_result_falls_back_to_empty_name(self):
        """没有对应 TOOL_START 的 TOOL_RESULT 不崩溃，name 为空字符串。"""
        events: list = []
        d = _MessageDispatcher(verbose=False)
        d.event_callback = events.append

        d.dispatch(_make_assistant_message(
            ToolResultBlock(tool_use_id="tu_orphan", content="ok", is_error=False)
        ))

        results = [e for e in events if e.event_type == EventType.TOOL_RESULT]
        assert len(results) == 1
        assert results[0].data.name == ""

    def test_pending_table_does_not_leak(self):
        """大量工具调用后 pending 表不应无限增长。"""
        d = _MessageDispatcher(verbose=False)
        for i in range(20):
            d.dispatch(_make_assistant_message(
                ToolUseBlock(id=f"tu_{i}", name="Write", input={"file_path": f"f{i}.py"})
            ))
            d.dispatch(_make_assistant_message(
                ToolResultBlock(tool_use_id=f"tu_{i}", content=None, is_error=False)
            ))
        # 所有都配对后 pending 应为空
        assert len(d._pending_tools) == 0


class TestToolFailureErrorType:
    """PostToolUseFailure Hook 注入的错误分类信息传播到事件中。"""

    def test_failure_event_carries_error_type(self):
        """工具执行失败的事件应携带 error_type 分类。"""
        events: list = []
        d = _MessageDispatcher(verbose=False)
        d.event_callback = events.append

        d.dispatch(_make_assistant_message(
            ToolUseBlock(id="tu_fail", name="Bash", input={"command": "false"})
        ))
        # 模拟 PostToolUseFailure 注入的错误信息
        d._record_tool_failure("tu_fail", "execution", "Exit code 1")
        d.dispatch(_make_assistant_message(
            ToolResultBlock(tool_use_id="tu_fail", content="", is_error=True)
        ))

        results = [e for e in events if e.event_type == EventType.TOOL_RESULT]
        assert len(results) >= 1
        # 最后一个结果应携带 error_type
        final = results[-1]
        assert final.data.is_error is True
        # error_type 来自 hook failure 记录
        assert getattr(final.data, 'error_type', None) == "execution"

    def test_permission_denied_error_type(self):
        """权限拒绝的错误类型为 'permission'。"""
        events: list = []
        d = _MessageDispatcher(verbose=False)
        d.event_callback = events.append

        d.dispatch(_make_assistant_message(
            ToolUseBlock(id="tu_perm", name="Read", input={"/etc/passwd": ""})
        ))
        d._record_tool_failure("tu_perm", "permission", "Path out of scope")
        d.dispatch(_make_assistant_message(
            ToolResultBlock(tool_use_id="tu_perm", content=None, is_error=True)
        ))

        results = [e for e in events if e.event_type == EventType.TOOL_RESULT]
        final = [r for r in results if r.data.tool_use_id == "tu_perm"][-1]
        assert getattr(final.data, 'error_type', None) == "permission"
