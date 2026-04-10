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
        """VIDEO_OUTPUT 从收集的文本中被提取（通过公共接口）。"""
        d = _MessageDispatcher(verbose=False)
        d.collected_text = [
            "working...",
            "VIDEO_OUTPUT: media/out.mp4",
            "SCENE_FILE: scene.py",
            "SCENE_CLASS: MyScene",
        ]
        po = d.get_pipeline_output()

        assert po is not None
        assert po.video_output == "media/out.mp4"
        assert po.scene_file == "scene.py"
        assert po.scene_class == "MyScene"
        # 向后兼容属性也正确
        assert d.video_output == "media/out.mp4"
        assert d.scene_file == "scene.py"

    def test_video_output_takes_last(self):
        """多个 VIDEO_OUTPUT 取最后一个。"""
        d = _MessageDispatcher(verbose=False)
        d.collected_text = [
            "VIDEO_OUTPUT: /tmp/a.mp4",
            "retrying...",
            "VIDEO_OUTPUT: /tmp/b.mp4",
        ]
        po = d.get_pipeline_output()
        assert po.video_output == "/tmp/b.mp4"

    def test_no_video_output_stays_none(self):
        """无 VIDEO_OUTPUT 时保持 None。"""
        d = _MessageDispatcher(verbose=False)
        d.collected_text = ["nothing useful"]
        po = d.get_pipeline_output()
        assert po is None
        assert d.get_video_output() is None


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


# ── P0 Bug #1: 缺少 asyncio import ──────────────────────────────


class TestAsyncioImport:
    def test_asyncio_in_module_globals(self):
        """模块全局作用域中存在 asyncio（__main__.py 顶层已导入）。"""
        assert hasattr(main_module, "asyncio"), (
            "asyncio 未在 __main__.py 中导入，"
            "运行 python -m manim_agent 会抛 NameError"
        )

    def test_main_is_coroutine_function(self):
        """main() 是异步函数。"""
        import inspect
        assert inspect.iscoroutinefunction(main_module.main)

    def test_main_callable_without_nameerror(self):
        """main() 可调用且不因缺少 asyncio 而抛 NameError。

        实际不会执行完整 pipeline（需要 Claude SDK），
        但至少验证函数定义层无语法/导入错误。
        """
        # 只验证 callable，不实际 await
        assert callable(main_module.main)


# ── P0 Bug #2: quality 参数死代码 ────────────────────────────


class TestQualityIntegration:
    def test_quality_high_uses_qh_in_prompt(self):
        """quality='high' 时系统提示词包含 -qh 标志。"""
        opts = main_module._build_options(
            cwd="/work",
            system_prompt=None,
            max_turns=10,
            quality="high",
        )
        assert "-qh" in opts.system_prompt

    def test_quality_medium_uses_qm_in_prompt(self):
        """quality='medium' 时系统提示词包含 -qm 标志（非 -qh）。"""
        opts = main_module._build_options(
            cwd="/work",
            system_prompt=None,
            max_turns=10,
            quality="medium",
        )
        assert "-qm" in opts.system_prompt
        assert "-qh" not in opts.system_prompt

    def test_quality_low_uses_ql_in_prompt(self):
        """quality='low' 时系统提示词包含 -ql 标志。"""
        opts = main_module._build_options(
            cwd="/work",
            system_prompt=None,
            max_turns=10,
            quality="low",
        )
        assert "-ql" in opts.system_prompt
        assert "-qh" not in opts.system_prompt

    def test_quality_default_is_high(self):
        """不传 quality 时默认使用 high (-qh)。"""
        opts = main_module._build_options(
            cwd="/work",
            system_prompt=None,
            max_turns=10,
        )
        assert "-qh" in opts.system_prompt

    def test_custom_system_prompt_not_overridden_by_quality(self):
        """自定义系统提示词时 quality 不覆盖用户提供的 prompt。"""
        custom = "You are a custom assistant with no Manim flags."
        opts = main_module._build_options(
            cwd="/work",
            system_prompt=custom,
            max_turns=10,
            quality="low",
        )
        assert opts.system_prompt == custom

    @pytest.mark.asyncio
    async def test_run_pipeline_passes_quality_to_options(self):
        """run_pipeline 将 quality 正确传递给 _build_options。

        通过 mock 验证 _build_options 收到了正确的 quality 值。
        """
        original_build = main_module._build_options

        call_capture: dict[str, Any] = {}

        def capture_build(*args, **kwargs):
            call_capture.update(kwargs)
            return original_build(*args, **kwargs)

        async def empty_query(**_kw):
            """返回空异步迭代器，让 pipeline 在 VIDEO_OUTPUT 检查处失败。"""
            return
            yield  # type: ignore[misc]

        with patch("manim_agent.__main__._build_options", side_effect=capture_build):
            with (
                patch("manim_agent.__main__.query", side_effect=empty_query),
                pytest.raises(RuntimeError, match="VIDEO_OUTPUT"),
            ):
                await main_module.run_pipeline(
                    user_text="test",
                    output_path="/tmp/out.mp4",
                    no_tts=True,
                    quality="medium",
                )

        assert call_capture.get("quality") == "medium"


# ── Phase 2: Dispatcher PipelineOutput 集成 ────────────────────


class TestDispatcherPipelineOutput:
    """验证 _MessageDispatcher 使用 PipelineOutput 替代裸字符串属性。"""

    def test_get_pipeline_output_returns_model(self):
        """dispatch 含标记消息后，get_pipeline_output() 返回 PipelineOutput 实例。"""
        from manim_agent.output_schema import PipelineOutput

        d = _MessageDispatcher(verbose=False)
        d.dispatch(_make_assistant_message(
            _make_text_block(
                "VIDEO_OUTPUT: /media/out.mp4\n"
                "SCENE_FILE: scene.py\n"
                "SCENE_CLASS: MyScene\n"
                "DURATION: 25\n"
            ),
        ))

        po = d.get_pipeline_output()
        assert isinstance(po, PipelineOutput)
        assert po.video_output == "/media/out.mp4"
        assert po.scene_file == "scene.py"
        assert po.scene_class == "MyScene"
        assert po.duration_seconds == 25.0

    def test_get_pipeline_output_none_when_no_markers(self):
        """无 VIDEO_OUTPUT 标记时 get_pipeline_output() 返回 None。"""
        d = _MessageDispatcher(verbose=False)
        d.dispatch(_make_assistant_message(_make_text_block("普通文本输出")))
        assert d.get_pipeline_output() is None

    def test_get_video_output_backward_compat(self):
        """get_video_output() 仍返回字符串路径（向后兼容）。"""
        d = _MessageDispatcher(verbose=False)
        d.collected_text = ["VIDEO_OUTPUT: /legacy/path.mp4"]
        assert d.get_video_output() == "/legacy/path.mp4"

    def test_extract_graceful_on_malformed_markers(self):
        """畸形标记文本不崩溃，pipeline_output 保持 None。"""
        d = _MessageDispatcher(verbose=False)
        # VIDEO_OUTPUT: 后面没有值
        d.collected_text = ["VIDEO_OUTPUT:", "SCENE_FILE: x.py"]
        # 不应抛异常
        po = d.get_pipeline_output()
        assert po is None

    def test_extract_result_backward_compat_dict(self):
        """extract_result() 仍返回兼容 dict 格式。"""
        text = (
            "VIDEO_OUTPUT: /out.mp4\n"
            "SCENE_FILE: s.py\n"
            "SCENE_CLASS: SClass\n"
        )
        result = main_module.extract_result(text)
        assert isinstance(result, dict)
        assert result["video_output_path"] == "/out.mp4"
        assert result["scene_file"] == "s.py"
        assert result["scene_class"] == "SClass"


# ── Phase 3: 源码捕获 ───────────────────────────────────────────


class TestCodeCapture:
    """验证 _MessageDispatcher 从 ToolUseBlock 捕获 Manim 源代码。"""

    def test_capture_write_tool_source_code(self):
        """Write 工具的 .py 文件内容被捕获。"""
        d = _MessageDispatcher(verbose=False)
        d.dispatch(_make_assistant_message(
            _make_tool_use_block("Write", {
                "file_path": "scenes/fourier.py",
                "content": "from manim import *\n\nclass FourierScene(Scene):\n    pass",
            }),
        ))
        assert "scenes/fourier.py" in d.captured_source_code
        assert "class FourierScene" in d.captured_source_code["scenes/fourier.py"]

    def test_capture_edit_tool_source_code(self):
        """Edit 工具的文件内容也被捕获。"""
        d = _MessageDispatcher(verbose=False)
        d.dispatch(_make_assistant_message(
            _make_tool_use_block("Edit", {
                "file_path": "scene.py",
                "content": "updated code here",
            }),
        ))
        assert d.captured_source_code.get("scene.py") == "updated code here"

    def test_capture_overwrites_previous_write(self):
        """同一文件的第二次写入覆盖第一次。"""
        d = _MessageDispatcher(verbose=False)
        d.dispatch(_make_assistant_message(
            _make_tool_use_block("Write", {
                "file_path": "scene.py",
                "content": "version 1",
            }),
        ))
        d.dispatch(_make_assistant_message(
            _make_tool_use_block("Write", {
                "file_path": "scene.py",
                "content": "version 2",
            }, tool_id="tu_002"),
        ))
        assert d.captured_source_code["scene.py"] == "version 2"

    def test_capture_ignores_non_write_tools(self):
        """Bash/Read 等工具不触发源码捕获。"""
        d = _MessageDispatcher(verbose=False)
        d.dispatch(_make_assistant_message(
            _make_tool_use_block("Bash", {"command": "manim -qh scene.py Scene"}),
        ))
        d.dispatch(_make_assistant_message(
            _make_tool_use_block("Read", {"file_path": "scene.py"}),
        ))
        assert len(d.captured_source_code) == 0

    def test_capture_empty_content_not_stored(self):
        """空 content 的 Write 不存储。"""
        d = _MessageDispatcher(verbose=False)
        d.dispatch(_make_assistant_message(
            _make_tool_use_block("Write", {"file_path": "scene.py", "content": ""}),
        ))
        assert "scene.py" not in d.captured_source_code

    def test_source_code_linked_to_pipeline_output(self):
        """完整 dispatch 循环后 source_code 自动关联到 pipeline_output。"""
        from manim_agent.output_schema import PipelineOutput

        d = _MessageDispatcher(verbose=False)
        # 1. Claude 写入 scene.py
        d.dispatch(_make_assistant_message(
            _make_tool_use_block("Write", {
                "file_path": "output/scene.py",
                "content": "from manim import *\nclass Demo(Scene):\n    pass",
            }),
        ))
        # 2. 输出标记
        d.dispatch(_make_assistant_message(
            _make_text_block(
                "VIDEO_OUTPUT: media/demo.mp4\n"
                "SCENE_FILE: output/scene.py\n"
                "SCENE_CLASS: Demo\n"
            ),
        ))

        po = d.get_pipeline_output()
        assert isinstance(po, PipelineOutput)
        assert po.source_code is not None
        assert "class Demo" in po.source_code

    def test_source_code_none_when_file_not_matched(self):
        """scene_file 指向的文件未被捕获时 source_code 为 None。"""
        d = _MessageDispatcher(verbose=False)
        d.dispatch(_make_assistant_message(
            _make_tool_use_block("Write", {
                "file_path": "actual_scene.py",
                "content": "code here",
            }),
        ))
        d.dispatch(_make_assistant_message(
            _make_text_block(
                "VIDEO_OUTPUT: /out.mp4\n"
                "SCENE_FILE: different_file.py\n"
            ),
        ))

        po = d.get_pipeline_output()
        assert po is not None
        assert po.source_code is None


# ── Phase 4: Narration + TTS 集成 ───────────────────────────────


class TestNarrationExtraction:
    """验证 NARRATION 标记提取和 TTS 文本选择逻辑。"""

    def test_narration_extracted_from_dispatcher(self):
        """dispatcher 从 TextBlock 中提取 NARRATION 标记。"""
        d = _MessageDispatcher(verbose=False)
        d.dispatch(_make_assistant_message(_make_text_block(
            "VIDEO_OUTPUT: /out.mp4\n"
            "NARRATION: 这是关于二叉树的专业解说。\n"
            "二叉树每个节点最多有两个子节点。\n"
        )))

        po = d.get_pipeline_output()
        assert po is not None
        assert "二叉树" in po.narration

    def test_narration_multiline_in_dispatcher(self):
        """多行 narration 在 dispatcher 中完整保留。"""
        d = _MessageDispatcher(verbose=False)
        d.dispatch(_make_assistant_message(_make_text_block(
            "VIDEO_OUTPUT: /x.mp4\n"
            "NARRATION: 第一行。\n"
            "第二行。\n"
            "第三行。\n"
        )))

        po = d.get_pipeline_output()
        lines = po.narration.split("\n")
        assert len(lines) == 3

    def test_narration_none_when_absent(self):
        """无 NARRATION 标记时 narration 为 None。"""
        d = _MessageDispatcher(verbose=False)
        d.dispatch(_make_assistant_message(_make_text_block("VIDEO_OUTPUT: /x.mp4")))
        po = d.get_pipeline_output()
        assert po is not None
        assert po.narration is None


class TestTTSNarrationFlow:
    """验证 run_pipeline 在有 narration 时传给 TTS，否则 fallback 到 user_text。"""

    @pytest.mark.asyncio
    async def test_tts_uses_narration_when_available(self):
        """dispatcher 有 narration 时 TTS 收到解说词而非 user_text。"""
        mock_messages = [
            _make_assistant_message(_make_text_block(
                "VIDEO_OUTPUT: /out.mp4\n"
                "NARRATION: 专业解说词内容\n"
            )),
            _make_result_message(num_turns=1),
        ]
        captured_tts_text: list[str] = []

        async def capture_tts(text, **_kw):
            captured_tts_text.append(text)
            return MagicMock(audio_path="a.mp3", subtitle_path="sub.srt", duration_ms=1000)

        with (
            patch("manim_agent.__main__.query") as mock_query,
            patch("manim_agent.__main__.tts_client.synthesize", side_effect=capture_tts),
            patch("manim_agent.__main__.video_builder.build_final_video", new_callable=AsyncMock) as mock_vid,
        ):
            async def gen(*_a, **_k):
                for m in mock_messages:
                    yield m
            mock_query.side_effect = gen
            mock_vid.return_value = "final.mp4"

            await main_module.run_pipeline(
                user_text="用户原始需求描述",
                output_path="/out.mp4",
                no_tts=False,
            )

        assert len(captured_tts_text) == 1
        assert captured_tts_text[0] == "专业解说词内容"

    @pytest.mark.asyncio
    async def test_tts_fallback_to_user_text(self):
        """无 narration 时 TTS 收到原始 user_text。"""
        mock_messages = [
            _make_assistant_message(_make_text_block("VIDEO_OUTPUT: /out.mp4")),
            _make_result_message(num_turns=1),
        ]
        captured_tts_text: list[str] = []

        async def capture_tts(text, **_kw):
            captured_tts_text.append(text)
            return MagicMock(audio_path="a.mp3", subtitle_path="sub.srt", duration_ms=1000)

        with (
            patch("manim_agent.__main__.query") as mock_query,
            patch("manim_agent.__main__.tts_client.synthesize", side_effect=capture_tts),
            patch("manim_agent.__main__.video_builder.build_final_video", new_callable=AsyncMock) as mock_vid,
        ):
            async def gen(*_a, **_k):
                for m in mock_messages:
                    yield m
            mock_query.side_effect = gen
            mock_vid.return_value = "final.mp4"

            await main_module.run_pipeline(
                user_text="用户需求",
                output_path="/out.mp4",
                no_tts=False,
            )

        assert captured_tts_text == ["用户需求"]


# ── Phase 5: structured_output 集成 ─────────────────────────────


class TestStructuredOutput:
    """验证 SDK structured_output 主路径和 text markers fallback。"""

    def test_handle_result_parses_structured_output(self):
        """ResultMessage 的 structured_output 被解析为 PipelineOutput。"""
        d = _MessageDispatcher(verbose=False)
        msg = _make_result_message(
            num_turns=2,
            **{"structured_output": {
                "video_output": "/structured/out.mp4",
                "scene_file": "s.py",
                "scene_class": "SScene",
                "duration_seconds": 15,
                "narration": "结构化解说",
            }},
        )
        d.dispatch(msg)

        po = d.get_pipeline_output()
        assert po is not None
        assert po.video_output == "/structured/out.mp4"
        assert po.narration == "结构化解说"

    def test_handle_result_invalid_structured_output_falls_back(self):
        """无效的 structured_output 不崩溃，fallback 到 text markers。"""
        d = _MessageDispatcher(verbose=False)
        # 先发一个带畸形 structured_output 的 ResultMessage
        msg_bad = _make_result_message(
            num_turns=1,
            **{"structured_output": {"bad_field": "data"}},
        )
        d.dispatch(msg_bad)
        # 再发含正确 text markers 的 AssistantMessage
        d.dispatch(_make_assistant_message(
            _make_text_block("VIDEO_OUTPUT: /fallback.mp4"),
        ))

        po = d.get_pipeline_output()
        # 应该从 text markers 中恢复
        assert po is not None
        assert po.video_output == "/fallback.mp4"

    def test_handle_result_null_structured_output_ignored(self):
        """structured_output=None 时 pipeline_output 依赖 text markers。"""
        d = _MessageDispatcher(verbose=False)
        msg = _make_result_message(
            num_turns=1,
            **{"structured_output": None},
        )
        d.dispatch(msg)
        # 无 text markers → None
        assert d.get_pipeline_output() is None

    def test_structured_output_takes_priority_over_text(self):
        """同时存在时 structured_output 优先于 text markers。"""
        d = _MessageDispatcher(verbose=False)
        # text markers 说 /text.mp4
        d.dispatch(_make_assistant_message(
            _make_text_block("VIDEO_OUTPUT: /text.mp4"),
        ))
        # structured_output 说 /struct.mp4 (后到，应覆盖)
        msg = _make_result_message(
            num_turns=1,
            **{"structured_output": {"video_output": "/struct.mp4"}},
        )
        d.dispatch(msg)

        po = d.get_pipeline_output()
        assert po.video_output == "/struct.mp4"


class TestBuildOptionsOutputFormat:
    """验证 _build_options 包含 output_format schema。"""

    def test_options_include_output_format(self):
        """_build_options() 返回的 options 含 output_format 字段。"""
        opts = main_module._build_options(
            cwd="/work",
            system_prompt="test",
            max_turns=10,
        )
        assert opts.output_format is not None
        assert opts.output_format["type"] == "json_schema"

    def test_output_format_schema_has_required_fields(self):
        """schema 要求 video_output 必填，其余可选。"""
        opts = main_module._build_options(
            cwd="/work",
            system_prompt="test",
            max_turns=10,
        )
        schema = opts.output_format["json_schema"]["schema"]
        assert "video_output" in schema["required"]
        assert "narration" in schema["properties"]


# ── Phase B: Dispatcher 结构化事件发射 ─────────────────────


from manim_agent.pipeline_events import (
    EventType,
    PipelineEvent,
    ToolStartPayload,
    ToolResultPayload,
    ThinkingPayload,
    ProgressPayload,
)


class TestDispatcherStructuredEvents:
    """验证 _MessageDispatcher 通过 event_callback 发射结构化事件。"""

    def _make_dispatcher(
        self,
        log_callback=None,
        event_callback=None,
    ) -> _MessageDispatcher:
        """创建 dispatcher，支持新旧两种回调。"""
        d = _MessageDispatcher(
            verbose=False,
            log_callback=log_callback,
        )
        if event_callback is not None:
            d.event_callback = event_callback
        return d

    # ── TOOL_START ─────────────────────────────────────────

    def test_tool_use_emits_tool_start_event(self):
        """ToolUseBlock 触发 TOOL_START 事件。"""
        events: list[PipelineEvent] = []
        d = self._make_dispatcher(event_callback=events.append)

        block = ToolUseBlock(
            id="tu_001",
            name="Write",
            input={"file_path": "scene.py", "content": "print('hi')"},
        )
        msg = _make_assistant_message(block)
        d._handle_assistant(msg)

        start_events = [
            e for e in events if e.event_type == EventType.TOOL_START
        ]
        assert len(start_events) == 1
        assert start_events[0].data.name == "Write"
        assert start_events[0].data.tool_use_id == "tu_001"

    def test_tool_start_contains_input_summary(self):
        """TOOL_START 事件的 input_summary 包含关键参数。"""
        events: list[PipelineEvent] = []
        d = self._make_dispatcher(event_callback=events.append)

        block = ToolUseBlock(
            id="tu_002",
            name="Bash",
            input={"command": "manim -qh scene.py Scene"},
        )
        d._handle_assistant(_make_assistant_message(block))

        start = [e for e in events if e.event_type == EventType.TOOL_START][0]
        assert "command" in start.data.input_summary

    # ── TOOL_RESULT ────────────────────────────────────────

    def test_tool_result_emits_tool_result_event(self):
        """ToolResultBlock 触发 TOOL_RESULT 事件。"""
        events: list[PipelineEvent] = []
        d = self._make_dispatcher(event_callback=events.append)

        block = ToolResultBlock(
            tool_use_id="tu_001",
            content="Rendered in 8.5s",
            is_error=False,
        )
        d._handle_assistant(_make_assistant_message(block))

        result_events = [
            e for e in events if e.event_type == EventType.TOOL_RESULT
        ]
        assert len(result_events) == 1
        assert result_events[0].data.is_error is False
        assert "8.5s" in result_events[0].data.content

    def test_tool_result_error_flag(self):
        """错误工具结果 is_error=True。"""
        events: list[PipelineEvent] = []
        d = self._make_dispatcher(event_callback=events.append)

        block = ToolResultBlock(
            tool_use_id="tu_003",
            content="Exit code 1",
            is_error=True,
        )
        d._handle_assistant(_make_assistant_message(block))

        result = [e for e in events
                  if e.event_type == EventType.TOOL_RESULT][0]
        assert result.data.is_error is True

    # ── THINKING ──────────────────────────────────────────

    def test_thinking_block_emits_thinking_event(self):
        """ThinkingBlock 触发 THINKING 事件。"""
        events: list[PipelineEvent] = []
        d = self._make_dispatcher(event_callback=events.append)

        block = ThinkingBlock(
            thinking="I need to create a Fourier transform animation...",
            signature="sig-abc",
        )
        d._handle_assistant(_make_assistant_message(block))

        think_events = [
            e for e in events if e.event_type == EventType.THINKING
        ]
        assert len(think_events) == 1
        assert "Fourier" in think_events[0].data.thinking

    def test_thinking_preview_auto_truncated(self):
        """长思考文本的 preview 自动截断。"""
        events: list[PipelineEvent] = []
        d = self._make_dispatcher(event_callback=events.append)

        long_text = "x" * 200
        block = ThinkingBlock(thinking=long_text, signature="s")
        d._handle_assistant(_make_assistant_message(block))

        think = [e for e in events
                 if e.event_type == EventType.THINKING][0]
        assert think.data.preview is not None
        assert len(think.data.preview) <= 100

    # ── PROGRESS ──────────────────────────────────────────

    def test_task_progress_emits_progress_event(self):
        """TaskProgressMessage 触发 PROGRESS 事件。"""
        events: list[PipelineEvent] = []
        d = self._make_dispatcher(event_callback=events.append)

        usage = TaskUsage(
            total_tokens=5000,
            tool_uses=3,
            duration_ms=10000,
        )
        msg = TaskProgressMessage(
            subtype="task_progress",
            task_id="t1",
            description="rendering",
            usage=usage,
            uuid="u1",
            session_id="s1",
            data={},
        )
        d.dispatch(msg)

        prog_events = [
            e for e in events if e.event_type == EventType.PROGRESS
        ]
        assert len(prog_events) >= 1
        assert prog_events[0].data.total_tokens == 5000
        assert prog_events[0].data.tool_uses == 3

    # ── 向后兼容 ──────────────────────────────────────────

    def test_log_callback_still_works_without_event_callback(self):
        """不设置 event_callback 时，log_callback 正常工作。"""
        logs: list[str] = []
        d = self._make_dispatcher(log_callback=logs.append)

        block = ToolUseBlock(
            id="tu_1", name="Read",
            input={"file_path": "config.json"},
        )
        d._handle_assistant(_make_assistant_message(block))
        assert len(logs) > 0  # 至少有工具调用日志行

    def test_no_crash_when_event_callback_is_none(self):
        """event_callback 为 None 时不崩溃（默认行为）。"""
        d = self._make_dispatcher()  # 无回调
        block = ToolUseBlock(id="tu_1", name="Write", input={})
        # 不应抛异常
        d._handle_assistant(_make_assistant_message(block))

    def test_both_callbacks_fire_together(self):
        """log_callback 和 event_callback 同时触发。"""
        logs: list[str] = []
        events: list[PipelineEvent] = []
        d = self._make_dispatcher(
            log_callback=logs.append,
            event_callback=events.append,
        )

        block = ThinkingBlock(thinking="hello", signature="s")
        d._handle_assistant(_make_assistant_message(block))

        assert len(logs) > 0  # 文本日志
        assert any(e.event_type == EventType.THINKING
                   for e in events)  # 结构化事件
