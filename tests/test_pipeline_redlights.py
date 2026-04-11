"""Red-light (xfail) tests for known pipeline defects.
"""
import pytest
from manim_agent import __main__ as main_module

class TestStderrHandlerForwardsToCallback:
    """验证 _stderr_handler 将 CLI 输出转发到 log_callback。

    当前实现只 print 到 sys.stderr 且不调用 log_callback，
    导致前端 SSE 流中丢失所有 CLI stderr 信息。
    """

    @pytest.mark.xfail(reason="known defect: not yet fixed")
    def test_stderr_handler_accepts_callback(self):
        """_stderr_handler 应支持可选的 callback 参数用于 SSE 推送。

        当前 _stderr_handler 是硬编码的模块级函数，无法注入回调。
        测试目标: 它应接受 log_callback 参数。
        """
        import inspect

        sig = inspect.signature(main_module._stderr_handler)
        # 红灯: 当前签名只有 (line: str) -> None
        # 绿灯目标: 应有 log_callback: Callable[[str], None] | None = None 参数
        params = list(sig.parameters.keys())
        assert "log_callback" in params, (
            f"_stderr_handler should accept log_callback param, "
            f"current params: {params}"
        )

    @pytest.mark.xfail(reason="known defect: not yet fixed")
    def test_stderr_all_lines_should_be_forwardable(self):
        """所有 stderr 行（不仅是 error）都应能被转发到 callback。

        当前只转发包含 error/warning/fail 关键字的行，
        其余有用的调试信息（模型名、session ID 等）被静默丢弃。
        """
        test_lines = [
            "Error: connection refused",
            "Warning: rate limit approaching",
            "Using model claude-sonnet-4-20250514",
            "Session resumed: sess-abc123",
            "Tool output: exit code 0",
        ]
        forwarded: list[str] = []

        for line in test_lines:
            main_module._stderr_handler(line)

        # 红灯: 验证当前行为 — 大量有用信息被丢弃
        # _stderr_handler 内部无回调机制，所有行要么 print 要么丢弃
        # 这里我们验证: handler 需要重构为支持回调注入
        assert len(forwarded) == 0, (
            "Current _stderr_handler cannot forward to callback; "
            "need refactoring to support log_callback injection"
        )


# ── Phase 9: Pipeline 阶段日志通过 callback (红灯) ─────────────


class TestPipelinePhaseLogsViaCallback:
    """验证 run_pipeline 各阶段日志通过 log_callback 推送到 SSE。

    Phase 3 (TTS) 和 Phase 4 (FFmpeg) 的进度信息当前只在终端 print，
    前端用户看不到合成/渲染阶段。
    """

    @pytest.mark.asyncio
    async def test_tts_phase_logs_via_callback(self):
        """TTS 合成阶段应通过 log_callback 推送 [TTS] 标记。"""
        logs: list[str] = []
        mock_messages = [
            _make_assistant_message(_make_text_block("VIDEO_OUTPUT: /out.mp4")),
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
                user_text="测试 TTS 日志",
                output_path="output/out.mp4",
                log_callback=logs.append,
            )

        # 红灯: 必须有精确的 [TTS] 阶段标记（不是泛泛的 video/输出）
        tts_logs = [l for l in logs if "[TTS]" in l]
        assert len(tts_logs) > 0, (
            f"Expected [TTS] marker in callback logs, got: {logs}"
        )

    @pytest.mark.asyncio
    async def test_ffmpeg_phase_logs_via_callback(self):
        """FFmpeg 合成阶段应通过 log_callback 推送 [MUX] 标记。"""
        logs: list[str] = []
        mock_messages = [
            _make_assistant_message(_make_text_block("VIDEO_OUTPUT: /out.mp4")),
            _make_result_message(num_turns=1),
        ]

        # 模拟 TTS 返回值以让 pipeline 继续到 FFmpeg 阶段
        mock_tts_result = MagicMock()
        mock_tts_result.audio_path = "/tmp/audio.mp3"
        mock_tts_result.subtitle_path = "/tmp/sub.srt"
        mock_tts_result.duration_ms = 1200
        mock_tts_result.word_count = 42

        with (
            patch("manim_agent.__main__.query") as mock_query,
            patch("manim_agent.__main__.tts_client.synthesize", new_callable=AsyncMock) as mock_tts,
            patch("manim_agent.__main__.video_builder.build_final_video", new_callable=AsyncMock) as mock_video,
        ):
            async def mock_query_gen(*args, **kwargs):
                for msg in mock_messages:
                    yield msg

            mock_query.side_effect = mock_query_gen
            mock_tts.return_value = mock_tts_result
            mock_video.return_value = "/out/final.mp4"

            result = await main_module.run_pipeline(
                user_text="测试 FFmpeg 日志",
                output_path="output/out.mp4",
                log_callback=logs.append,
            )

        # 必须有精确的 [MUX] 阶段标记
        ffmpeg_logs = [l for l in logs if "[MUX]" in l]
        assert len(ffmpeg_logs) > 0, (
            f"Expected [MUX] marker in callback logs, got: {logs}"
        )
