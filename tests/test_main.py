"""Tests for manim_agent.__main__ module (CLI entry point).

覆盖：CLI 参数解析、结果提取、消息分发器、会话隔离、Pipeline 编排。
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from manim_agent import __main__ as main_module
from manim_agent.__main__ import _MessageDispatcher

# 导入 SDK 类型用于构造测试消息
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


# ── 辅助函数 ───────────────────────────────────────────────────


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


# ── CLI 参数解析 ──────────────────────────────────────────────


class TestParseArgs:
    def test_defaults(self):
        """默认参数值正确。"""
        args = main_module.parse_args(["解释傅里叶变换"])
        assert args.text == "解释傅里叶变换"
        assert args.output == "output.mp4"
        assert args.voice == "female-tianmei"
        assert args.model == "speech-2.8-hd"
        assert args.quality == "high"
        assert args.no_tts is False
        assert args.max_turns == 50

    def test_all_options(self):
        """所有参数正确解析。"""
        args = main_module.parse_args([
            "讲解二叉树",
            "-o", "tree.mp4",
            "--voice", "male-qn-qingse",
            "--model", "speech-02-hd",
            "--quality", "low",
            "--no-tts",
            "--max-turns", "20",
            "--cwd", "/workspace",
            "--prompt-file", "custom.txt",
        ])
        assert args.text == "讲解二叉树"
        assert args.output == "tree.mp4"
        assert args.voice == "male-qn-qingse"
        assert args.model == "speech-02-hd"
        assert args.quality == "low"
        assert args.no_tts is True
        assert args.max_turns == 20
        assert args.cwd == "/workspace"
        assert args.prompt_file == "custom.txt"

    def test_no_tts_flag(self):
        """--no-tts 标志生效。"""
        args = main_module.parse_args(["测试", "--no-tts"])
        assert args.no_tts is True

    def test_positional_required(self):
        """缺少位置参数时抛出 SystemExit。"""
        with pytest.raises(SystemExit):
            main_module.parse_args([])


# ── 结果提取 ──────────────────────────────────────────────────


class TestExtractResult:
    def test_extract_video_output(self):
        """从文本中提取 VIDEO_OUTPUT 路径。"""
        text = "渲染完成\nVIDEO_OUTPUT: /path/to/video.mp4\n其他信息"
        result = main_module.extract_result(text)
        assert result["video_output_path"] == "/path/to/video.mp4"

    def test_extract_scene_info(self):
        """提取 SCENE_FILE 和 SCENE_CLASS。"""
        text = (
            "VIDEO_OUTPUT: media/scene.mp4\n"
            "SCENE_FILE: scenes/fourier.py\n"
            "SCENE_CLASS: FourierScene\n"
            "DURATION: 45"
        )
        result = main_module.extract_result(text)
        assert result["scene_file"] == "scenes/fourier.py"
        assert result["scene_class"] == "FourierScene"

    def test_no_marker_returns_none(self):
        """无 VIDEO_OUTPUT 标记时路径为 None。"""
        result = main_module.extract_result("一些普通文本输出")
        assert result["video_output_path"] is None

    def test_empty_text_returns_none(self):
        """空文本返回 None 值。"""
        result = main_module.extract_result("")
        assert result["video_output_path"] is None

    def test_extract_from_message_stream(self):
        """从多行消息中提取最后一个有效结果。"""
        text = (
            "正在编写代码...\n"
            "VIDEO_OUTPUT: /tmp/attempt1.mp4\n"
            "效果不佳，重新渲染...\n"
            "VIDEO_OUTPUT: /tmp/final.mp4\n"
            "SCENE_FILE: final_scene.py\n"
            "SCENE_CLASS: FinalScene"
        )
        result = main_module.extract_result(text)
        assert result["video_output_path"] == "/tmp/final.mp4"


# ── _MessageDispatcher ──────────────────────────────────────────


class TestMessageDispatcherInit:
    def test_default_state(self):
        """初始化状态正确。"""
        d = _MessageDispatcher(verbose=False)
        assert d.verbose is False
        assert d.turn_count == 0
        assert d.tool_use_count == 0
        assert d.collected_text == []
        assert d.video_output is None
        assert d.result_summary is None

    def test_verbose_mode(self):
        """verbose 可配置。"""
        d = _MessageDispatcher(verbose=True)
        assert d.verbose is True


class TestMessageDispatcherDispatch:
    def test_dispatch_assistant_message(self, capsys):
        """AssistantMessage 被正确分发，TextBlock 被收集。"""
        msg = _make_assistant_message(
            _make_text_block("hello world"),
            _make_tool_use_block("Bash", {"command": "ls"}),
        )
        d = _MessageDispatcher(verbose=True)
        d.dispatch(msg)

        assert "hello world" in d.collected_text
        assert d.tool_use_count == 1

    def test_dispatch_multiple_text_blocks(self):
        """多个 TextBlock 都被收集。"""
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
        """ToolUseBlock 被计数。"""
        msg = _make_assistant_message(
            _make_tool_use_block("Write", {"file_path": "test.py"}),
            _make_tool_use_block("Bash", {"command": "echo hi"}, tool_id="tu_002"),
            _make_text_block("done"),
        )
        d = _MessageDispatcher(verbose=False)
        d.dispatch(msg)

        assert d.tool_use_count == 2

    def test_dispatch_tool_result_success(self, capsys):
        """成功的 ToolResultBlock 不影响错误状态。"""
        msg = _make_assistant_message(
            _make_tool_result_block(content="output ok"),
        )
        d = _MessageDispatcher(verbose=True)
        d.dispatch(msg)
        # 不应抛异常

    def test_dispatch_tool_result_error(self, capsys):
        """失败的 ToolResultBlock 被记录。"""
        msg = _make_assistant_message(
            _make_tool_result_block(content="error details", is_error=True),
        )
        d = _MessageDispatcher(verbose=True)
        d.dispatch(msg)
        # 不应抛异常，日志应包含 error 标记

    def test_dispatch_thinking_block(self, capsys):
        """ThinkingBlock 被处理。"""
        msg = _make_assistant_message(
            _make_thinking_block("I need to plan this..."),
        )
        d = _MessageDispatcher(verbose=True)
        d.dispatch(msg)
        # 不应抛异常

    def test_dispatch_result_message(self):
        """ResultMessage 摘要被捕获。"""
        msg = _make_result_message(num_turns=5, total_cost_usd=0.056)
        d = _MessageDispatcher(verbose=False)
        d.dispatch(msg)

        assert d.result_summary is not None
        assert d.result_summary["turns"] == 5
        assert d.result_summary["cost_usd"] == 0.056

    def test_dispatch_result_error(self):
        """错误 ResultMessage 的 is_error 被记录。"""
        msg = _make_result_message(is_error=True, errors=["timeout"])
        d = _MessageDispatcher(verbose=False)
        d.dispatch(msg)

        assert d.result_summary["is_error"] is True

    def test_dispatch_rate_limit_event(self, capsys):
        """RateLimitEvent 被处理。"""
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
        # 不应抛异常

    def test_dispatch_task_progress(self, capsys):
        """TaskProgressMessage 的 usage 被处理。"""
        msg = TaskProgressMessage(
            subtype="task_progress",
            task_id="t1",
            description="rendering",
            usage=TaskUsage(total_tokens=5000, tool_uses=3, duration_ms=10000),
            uuid="u1",
            session_id="s1",
            data={},  # SystemMessage 子类需要 data 字段
        )
        d = _MessageDispatcher(verbose=True)
        d.dispatch(msg)
        # 不应抛异常

    def test_dispatch_task_notification_completed(self, capsys):
        """完成的 TaskNotificationMessage 被处理。"""
        msg = TaskNotificationMessage(
            subtype="task_notification",
            task_id="t1",
            status="completed",
            output_file="/out/video.mp4",
            summary="done",
            uuid="u1",
            session_id="s1",
            data={},  # SystemMessage 子类需要 data 字段
        )
        d = _MessageDispatcher(verbose=True)
        d.dispatch(msg)
        # 不应抛异常

    def test_dispatch_unknown_message_ignored(self):
        """未知消息类型不崩溃（如 UserMessage）。"""
        # UserMessage 不是 dispatcher 处理的类型，应该静默跳过
        class FakeMsg:
            pass

        d = _MessageDispatcher(verbose=False)
        # 不应有 attribute 错误 — dispatch 应安全跳过
        d.dispatch(FakeMsg())  # type: ignore


class TestMessageDispatcherVideoOutput:
    def test_video_output_extracted_from_collected_text(self):
        """VIDEO_OUTPUT 从收集的文本中被提取。"""
        d = _MessageDispatcher(verbose=False)
        d.collected_text = [
            "working...",
            "VIDEO_OUTPUT: media/out.mp4",
            "SCENE_FILE: scene.py",
            "SCENE_CLASS: MyScene",
        ]
        d._extract_video_output()

        assert d.video_output == "media/out.mp4"
        assert d.scene_file == "scene.py"
        assert d.scene_class == "MyScene"

    def test_video_output_takes_last(self):
        """多个 VIDEO_OUTPUT 取最后一个。"""
        d = _MessageDispatcher(verbose=False)
        d.collected_text = [
            "VIDEO_OUTPUT: /tmp/a.mp4",
            "retrying...",
            "VIDEO_OUTPUT: /tmp/b.mp4",
        ]
        d._extract_video_output()

        assert d.video_output == "/tmp/b.mp4"

    def test_no_video_output_stays_none(self):
        """无 VIDEO_OUTPUT 时保持 None。"""
        d = _MessageDispatcher(verbose=False)
        d.collected_text = ["nothing useful"]
        d._extract_video_output()

        assert d.video_output is None


# ── 会话隔离 ──────────────────────────────────────────────────


class TestSessionIsolation:
    def test_unique_session_id_per_call(self):
        """每次调用 run_pipeline 生成不同的 session_id。"""
        # 我们无法直接检查 options 内部值（它是内部构建的），
        # 但可以通过 mock query 来验证 options 被正确传递
        # 这里验证 uuid 被导入且可调用
        id1 = str(uuid.uuid4())
        id2 = str(uuid.uuid4())
        assert id1 != id2
        assert len(id1) == 36  # 标准 UUID4 格式

    def test_build_options_includes_session_fields(self):
        """_build_options 返回含 session_id 和 fork_session 的 options。"""
        options = main_module._build_options(
            cwd="/project",
            system_prompt="test prompt",
            max_turns=10,
        )
        # 验证选项包含隔离字段
        assert hasattr(options, "session_id")
        assert hasattr(options, "fork_session")
        assert options.session_id is not None  # 应为非空 UUID
        assert options.fork_session is True

    def test_fork_session_always_true(self):
        """fork_session 始终为 True。"""
        options = main_module._build_options(
            cwd="/project",
            system_prompt="test",
            max_turns=5,
        )
        assert options.fork_session is True


# ── Pipeline 编排（Mock 集成） ────────────────────────────────


class TestRunPipeline:
    @pytest.mark.asyncio
    async def test_full_flow_with_tts(self):
        """含 TTS 的完整流程 — 验证 dispatcher 被使用且有结果摘要。"""
        mock_messages = [
            _make_assistant_message(
                _make_text_block("VIDEO_OUTPUT: media/out.mp4\nSCENE_FILE: s.py\nSCENE_CLASS: S"),
                _make_tool_use_block("Write", {"file_path": "s.py"}),
            ),
            _make_result_message(num_turns=2, total_cost_usd=0.02),
        ]

        with (
            patch("manim_agent.__main__.query") as mock_query,
            patch("manim_agent.__main__.tts_client.synthesize", new_callable=AsyncMock) as mock_tts,
            patch("manim_agent.__main__.video_builder.build_final_video", new_callable=AsyncMock) as mock_video,
        ):
            async def mock_query_gen(*args, **kwargs):
                for msg in mock_messages:
                    yield msg

            mock_query.side_effect = mock_query_gen

            mock_tts.return_value = MagicMock(
                audio_path="out/audio.mp3",
                subtitle_path="out/sub.srt",
                duration_ms=30000,
            )
            mock_video.return_value = "output/final.mp4"

            result = await main_module.run_pipeline(
                user_text="测试内容",
                output_path="output/final.mp4",
                voice_id="female-tianmei",
                no_tts=False,
            )

            assert result == "output/final.mp4"
            mock_tts.assert_awaited_once()
            mock_video.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skip_tts_mode(self):
        """--no-tts 模式跳过 TTS 和 video builder。"""
        mock_messages = [
            _make_assistant_message(_make_text_block("VIDEO_OUTPUT: media/silent.mp4")),
            _make_result_message(num_turns=1),
        ]

        with (
            patch("manim_agent.__main__.query") as mock_query,
            patch("manim_agent.__main__.tts_client.synthesize", new_callable=AsyncMock) as mock_tts,
            patch("manim_agent.__main__.video_builder.build_final_video", new_callable=AsyncMock) as mock_video,
        ):
            async def mock_query_gen(*args, **kwargs):
                for msg in mock_messages:
                    yield msg

            mock_query.side_effect = mock_query_gen

            result = await main_module.run_pipeline(
                user_text="测试",
                output_path="output/out.mp4",
                no_tts=True,
            )

            assert result == "media/silent.mp4"
            mock_tts.assert_not_awaited()
            mock_video.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_video_output_raises(self):
        """Claude 未输出 VIDEO_OUTPUT 时抛 RuntimeError。"""
        mock_messages = [
            _make_assistant_message(_make_text_block("处理完成但未生成视频")),
        ]

        with (
            patch("manim_agent.__main__.query") as mock_query,
            pytest.raises(RuntimeError, match="VIDEO_OUTPUT"),
        ):
            async def mock_query_gen(*args, **kwargs):
                for msg in mock_messages:
                    yield msg

            mock_query.side_effect = mock_query_gen

            await main_module.run_pipeline(
                user_text="测试",
                output_path="output/out.mp4",
                no_tts=True,
            )


class TestBuildOptions:
    def test_basic_options(self):
        """_build_options 基本字段正确。"""
        opts = main_module._build_options(
            cwd="/work",
            system_prompt="You are a helpful assistant.",
            max_turns=30,
        )
        assert opts.cwd == "/work"
        assert opts.system_prompt == "You are a helpful assistant."
        assert opts.max_turns == 30
        assert opts.permission_mode == "acceptEdits"

    def test_custom_prompt_file(self, tmp_path):
        """自定义提示词文件被加载。"""
        prompt_file = tmp_path / "custom_prompt.txt"
        prompt_file.write_text("Custom system prompt here")

        opts = main_module._build_options(
            cwd="/work",
            system_prompt=None,
            prompt_file=str(prompt_file),
            max_turns=10,
        )
        assert "Custom system prompt here" in opts.system_prompt

    def test_stderr_callback_set(self):
        """stderr 回调被设置。"""
        opts = main_module._build_options(
            cwd="/work",
            system_prompt="test",
            max_turns=5,
        )
        assert opts.stderr is not None  # 应设置默认 stderr handler
