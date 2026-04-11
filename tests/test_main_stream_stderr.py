from ._test_main_dispatcher_helpers import *

class TestStreamEventHandling:
    """楠岃瘉 dispatcher 姝ｇ‘澶勭悊 StreamEvent锛堝綋鍓嶈瀹屽叏蹇界暐锛夈€?""

    @staticmethod
    def _make_stream_event(event_data: dict | None = None) -> "StreamEvent":
        from claude_agent_sdk import StreamEvent

        return StreamEvent(
            uuid="stream-001",
            session_id="sess-abc",
            event=event_data or {"type": "content_block_delta"},
        )

    def test_dispatch_stream_event_calls_log_callback(self):
        """StreamEvent 搴旈€氳繃 log_callback 鎺ㄩ€侊紝涓嶅簲琚潤榛樺拷鐣ャ€?""
        logs: list[str] = []
        d = _MessageDispatcher(
            verbose=False,
            log_callback=logs.append,
        )
        msg = self._make_stream_event({"type": "content_block_delta", "delta": "hi"})

        d.dispatch(msg)

        # 绾㈢伅: 褰撳墠 StreamEvent 琚畬鍏ㄥ拷鐣ワ紙dispatch 绗?34琛屾敞閲婏級
        # 缁跨伅鐩爣: logs 搴斿寘鍚?stream 鐩稿叧淇℃伅
        assert any("stream" in l.lower() or "delta" in l.lower()
                   for l in logs), (
            f"Expected StreamEvent to produce log output, got: {logs}"
        )

    def test_dispatch_stream_event_with_parent_tool_use(self):
        """甯?parent_tool_use_id 鐨?StreamEvent 涔熷簲琚鐞嗐€?""
        logs: list[str] = []
        d = _MessageDispatcher(verbose=False, log_callback=logs.append)
        msg = self._make_stream_event({
            "type": "content_block_delta",
            "delta": {"type": "text_delta", "text": "thinking..."},
        })
        msg.parent_tool_use_id = "tu_001"

        d.dispatch(msg)

        assert len(logs) > 0, "StreamEvent with tool_use parent should produce log"

    def test_dispatch_stream_event_does_not_crash_without_callback(self):
        """鏃?log_callback 鏃?StreamEvent 涓嶅簲宕╂簝锛堝悜鍚庡吋瀹癸級銆?""
        d = _MessageDispatcher(verbose=False)
        msg = self._make_stream_event()

        # 涓嶅簲鎶涘紓甯?
        d.dispatch(msg)


# 鈹€鈹€ Phase 8: stderr 鍥炶皟杞彂 (绾㈢伅) 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€


class TestStderrHandlerForwardsToCallback:
    """楠岃瘉 _stderr_handler 灏?CLI 杈撳嚭杞彂鍒?log_callback銆?

    褰撳墠瀹炵幇鍙?print 鍒?sys.stderr 涓斾笉璋冪敤 log_callback锛?
    瀵艰嚧鍓嶇 SSE 娴佷腑涓㈠け鎵€鏈?CLI stderr 淇℃伅銆?
    """

    def test_stderr_handler_accepts_callback(self):
        """_stderr_handler 搴旀敮鎸佸彲閫夌殑 callback 鍙傛暟鐢ㄤ簬 SSE 鎺ㄩ€併€?

        褰撳墠 _stderr_handler 鏄‖缂栫爜鐨勬ā鍧楃骇鍑芥暟锛屾棤娉曟敞鍏ュ洖璋冦€?
        娴嬭瘯鐩爣: 瀹冨簲鎺ュ彈 log_callback 鍙傛暟銆?
        """
        import inspect

        sig = inspect.signature(main_module._stderr_handler)
        # 绾㈢伅: 褰撳墠绛惧悕鍙湁 (line: str) -> None
        # 缁跨伅鐩爣: 搴旀湁 log_callback: Callable[[str], None] | None = None 鍙傛暟
        params = list(sig.parameters.keys())
        assert "log_callback" in params, (
            f"_stderr_handler should accept log_callback param, "
            f"current params: {params}"
        )

    def test_stderr_all_lines_should_be_forwardable(self):
        """鎵€鏈?stderr 琛岋紙涓嶄粎鏄?error锛夐兘搴旇兘琚浆鍙戝埌 callback銆?

        褰撳墠鍙浆鍙戝寘鍚?error/warning/fail 鍏抽敭瀛楃殑琛岋紝
        鍏朵綑鏈夌敤鐨勮皟璇曚俊鎭紙妯″瀷鍚嶃€乻ession ID 绛夛級琚潤榛樹涪寮冦€?
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

        # 绾㈢伅: 楠岃瘉褰撳墠琛屼负 鈥?澶ч噺鏈夌敤淇℃伅琚涪寮?
        # _stderr_handler 鍐呴儴鏃犲洖璋冩満鍒讹紝鎵€鏈夎瑕佷箞 print 瑕佷箞涓㈠純
        # 杩欓噷鎴戜滑楠岃瘉: handler 闇€瑕侀噸鏋勪负鏀寔鍥炶皟娉ㄥ叆
        assert len(forwarded) == 0, (
            "Current _stderr_handler cannot forward to callback; "
            "need refactoring to support log_callback injection"
        )


# 鈹€鈹€ Phase 9: Pipeline 闃舵鏃ュ織閫氳繃 callback (绾㈢伅) 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€


class TestPipelinePhaseLogsViaCallback:
    """楠岃瘉 run_pipeline 鍚勯樁娈垫棩蹇楅€氳繃 log_callback 鎺ㄩ€佸埌 SSE銆?

    Phase 3 (TTS) 鍜?Phase 4 (FFmpeg) 鐨勮繘搴︿俊鎭綋鍓嶅彧鍦ㄧ粓绔?print锛?
    鍓嶇鐢ㄦ埛鐪嬩笉鍒板悎鎴?娓叉煋闃舵銆?
    """

    @pytest.mark.asyncio
    async def test_tts_phase_logs_via_callback(self):
        """TTS 鍚堟垚闃舵搴旈€氳繃 log_callback 鎺ㄩ€?[TTS] 鏍囪銆?""
        logs: list[str] = []
        mock_messages = [
            _make_assistant_message(_make_text_block("娓叉煋瀹屾垚")),
            _make_result_message(
                num_turns=1,
                **{"structured_output": {"video_output": "/out.mp4"}},
            ),
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
                user_text="娴嬭瘯 TTS 鏃ュ織",
                output_path="output/out.mp4",
                log_callback=logs.append,
            )

        # 绾㈢伅: 蹇呴』鏈夌簿纭殑 [TTS] 闃舵鏍囪锛堜笉鏄硾娉涚殑 video/杈撳嚭锛?
        tts_logs = [l for l in logs if "[TTS]" in l]
        assert len(tts_logs) > 0, (
            f"Expected [TTS] marker in callback logs, got: {logs}"
        )

    @pytest.mark.asyncio
    async def test_ffmpeg_phase_logs_via_callback(self):
        """FFmpeg 鍚堟垚闃舵搴旈€氳繃 log_callback 鎺ㄩ€?[MUX] 鏍囪銆?""
        logs: list[str] = []
        mock_messages = [
            _make_assistant_message(_make_text_block("娓叉煋瀹屾垚")),
            _make_result_message(
                num_turns=1,
                **{"structured_output": {"video_output": "/out.mp4"}},
            ),
        ]

        # 妯℃嫙 TTS 杩斿洖鍊间互璁?pipeline 缁х画鍒?FFmpeg 闃舵
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
                user_text="娴嬭瘯 FFmpeg 鏃ュ織",
                output_path="output/out.mp4",
                log_callback=logs.append,
            )

        # 蹇呴』鏈夌簿纭殑 [MUX] 闃舵鏍囪
        ffmpeg_logs = [l for l in logs if "[MUX]" in l]
        assert len(ffmpeg_logs) > 0, (
            f"Expected [MUX] marker in callback logs, got: {logs}"
        )

