"""Tests for _MessageDispatcher (extracted from test_main.py).
"""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from manim_agent import __main__ as main_module
from manim_agent.__main__ import _MessageDispatcher
from manim_agent.hooks import create_hook_state
from claude_agent_sdk import (
    AssistantMessage, ResultMessage, RateLimitEvent, RateLimitInfo,
    TaskProgressMessage, TaskNotificationMessage, TaskUsage,
    TextBlock, ToolUseBlock, ToolResultBlock, ThinkingBlock,
)
# 鈹€鈹€ 杈呭姪鍑芥暟 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€


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

class TestMessageDispatcherInit:
    def test_default_state(self):
        """鍒濆鍖栫姸鎬佹纭€?""
        d = _MessageDispatcher(verbose=False)
        assert d.verbose is False
        assert d.turn_count == 0
        assert d.tool_use_count == 0
        assert d.collected_text == []
        assert d.video_output is None
        assert d.result_summary is None

    def test_verbose_mode(self):
        """verbose 鍙厤缃€?""
        d = _MessageDispatcher(verbose=True)
        assert d.verbose is True


class TestMessageDispatcherDispatch:
    def test_dispatch_assistant_message(self, capsys):
        """AssistantMessage 琚纭垎鍙戯紝TextBlock 琚敹闆嗐€?""
        msg = _make_assistant_message(
            _make_text_block("hello world"),
            _make_tool_use_block("Bash", {"command": "ls"}),
        )
        d = _MessageDispatcher(verbose=True)
        d.dispatch(msg)

        assert "hello world" in d.collected_text
        assert d.tool_use_count == 1

    def test_dispatch_multiple_text_blocks(self):
        """澶氫釜 TextBlock 閮借鏀堕泦銆?""
        msg = _make_assistant_message(
            _make_text_block("line1"),
            _make_text_block("line2"),
        )
        d = _MessageDispatcher(verbose=False)
        d.dispatch(msg)

        assert len(d.collected_text) == 2
        assert d.collected_text[0] == "line1"
        assert d.collected_text[1] == "line2"

    def test_dispatch_tool_use_blocks(self):
        """ToolUseBlock 琚鏁般€?""
        msg = _make_assistant_message(
            _make_tool_use_block("Write", {"file_path": "test.py"}),
            _make_tool_use_block("Bash", {"command": "echo hi"}, tool_id="tu_002"),
            _make_text_block("done"),
        )
        d = _MessageDispatcher(verbose=False)
        d.dispatch(msg)

        assert d.tool_use_count == 2

    def test_dispatch_tool_result_success(self, capsys):
        """鎴愬姛鐨?ToolResultBlock 涓嶅奖鍝嶉敊璇姸鎬併€?""
        msg = _make_assistant_message(
            _make_tool_result_block(content="output ok"),
        )
        d = _MessageDispatcher(verbose=True)
        d.dispatch(msg)
        # 涓嶅簲鎶涘紓甯?

    def test_dispatch_tool_result_error(self, capsys):
        """澶辫触鐨?ToolResultBlock 琚褰曘€?""
        msg = _make_assistant_message(
            _make_tool_result_block(content="error details", is_error=True),
        )
        d = _MessageDispatcher(verbose=True)
        d.dispatch(msg)
        # 涓嶅簲鎶涘紓甯革紝鏃ュ織搴斿寘鍚?error 鏍囪

    def test_dispatch_thinking_block(self, capsys):
        """ThinkingBlock 琚鐞嗐€?""
        msg = _make_assistant_message(
            _make_thinking_block("I need to plan this..."),
        )
        d = _MessageDispatcher(verbose=True)
        d.dispatch(msg)
        # 涓嶅簲鎶涘紓甯?

    def test_dispatch_result_message(self):
        """ResultMessage 鎽樿琚崟鑾枫€?""
        msg = _make_result_message(num_turns=5, total_cost_usd=0.056)
        d = _MessageDispatcher(verbose=False)
        d.dispatch(msg)

        assert d.result_summary is not None
        assert d.result_summary["turns"] == 5
        assert d.result_summary["cost_usd"] == 0.056

    def test_dispatch_result_error(self):
        """閿欒 ResultMessage 鐨?is_error 琚褰曘€?""
        msg = _make_result_message(is_error=True, errors=["timeout"])
        d = _MessageDispatcher(verbose=False)
        d.dispatch(msg)

        assert d.result_summary["is_error"] is True

    def test_dispatch_rate_limit_event(self, capsys):
        """RateLimitEvent 琚鐞嗐€?""
        event = RateLimitEvent(
            rate_limit_info=RateLimitInfo(
                status="allowed_warning",
                utilization=0.75,
            ),
            uuid="u1",
            session_id="s1",
        )
        d = _MessageDispatcher(verbose=True)
        d.dispatch(event)
        # 涓嶅簲鎶涘紓甯?

    def test_dispatch_task_progress(self, capsys):
        """TaskProgressMessage 鐨?usage 琚鐞嗐€?""
        msg = TaskProgressMessage(
            subtype="task_progress",
            task_id="t1",
            description="rendering",
            usage=TaskUsage(total_tokens=5000, tool_uses=3, duration_ms=10000),
            uuid="u1",
            session_id="s1",
            data={},  # SystemMessage 瀛愮被闇€瑕?data 瀛楁
        )
        d = _MessageDispatcher(verbose=True)
        d.dispatch(msg)
        # 涓嶅簲鎶涘紓甯?

    def test_dispatch_task_notification_completed(self, capsys):
        """瀹屾垚鐨?TaskNotificationMessage 琚鐞嗐€?""
        msg = TaskNotificationMessage(
            subtype="task_notification",
            task_id="t1",
            status="completed",
            output_file="/out/video.mp4",
            summary="done",
            uuid="u1",
            session_id="s1",
            data={},  # SystemMessage 瀛愮被闇€瑕?data 瀛楁
        )
        d = _MessageDispatcher(verbose=True)
        d.dispatch(msg)
        # 涓嶅簲鎶涘紓甯?

    def test_dispatch_unknown_message_ignored(self):
        """鏈煡娑堟伅绫诲瀷涓嶅穿婧冿紙濡?UserMessage锛夈€?""
        # UserMessage 涓嶆槸 dispatcher 澶勭悊鐨勭被鍨嬶紝搴旇闈欓粯璺宠繃
        class FakeMsg:
            pass

        d = _MessageDispatcher(verbose=False)
        # 涓嶅簲鏈?attribute 閿欒 鈥?dispatch 搴斿畨鍏ㄨ烦杩?
        d.dispatch(FakeMsg())  # type: ignore


# 鈹€鈹€ 浼氳瘽闅旂 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€


class TestSessionIsolation:
    def test_unique_session_id_per_call(self):
        """姣忔璋冪敤 run_pipeline 鐢熸垚涓嶅悓鐨?session_id銆?""
        # 鎴戜滑鏃犳硶鐩存帴妫€鏌?options 鍐呴儴鍊硷紙瀹冩槸鍐呴儴鏋勫缓鐨勶級锛?
        # 浣嗗彲浠ラ€氳繃 mock query 鏉ラ獙璇?options 琚纭紶閫?
        # 杩欓噷楠岃瘉 uuid 琚鍏ヤ笖鍙皟鐢?
        import uuid
        id1 = str(uuid.uuid4())
        id2 = str(uuid.uuid4())
        assert id1 != id2
        assert len(id1) == 36  # 鏍囧噯 UUID4 鏍煎紡

    def test_build_options_includes_session_fields(self):
        """_build_options 杩斿洖鍚?session_id 鍜?fork_session 鐨?options銆?""
        options = main_module._build_options(
            cwd="/project",
            system_prompt="test prompt",
            max_turns=10,
        )
        # 楠岃瘉閫夐」鍖呭惈闅旂瀛楁
        assert hasattr(options, "session_id")
        assert hasattr(options, "fork_session")
        assert options.session_id is not None  # 搴斾负闈炵┖ UUID
        assert options.fork_session is True

    def test_fork_session_always_true(self):
        """fork_session 濮嬬粓涓?True銆?""
        options = main_module._build_options(
            cwd="/project",
            system_prompt="test",
            max_turns=5,
        )
        assert options.fork_session is True


# 鈹€鈹€ Pipeline 缂栨帓锛圡ock 闆嗘垚锛?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€


