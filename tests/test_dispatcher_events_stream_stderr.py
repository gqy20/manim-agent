from ._test_main_dispatcher_helpers import *

class TestDispatcherStructuredEvents:
    """楠岃瘉 _MessageDispatcher 閫氳繃 event_callback 鍙戝皠缁撴瀯鍖栦簨浠躲€?""

    def _make_dispatcher(
        self,
        log_callback=None,
        event_callback=None,
    ) -> _MessageDispatcher:
        """鍒涘缓 dispatcher锛屾敮鎸佹柊鏃т袱绉嶅洖璋冦€?""
        d = _MessageDispatcher(
            verbose=False,
            log_callback=log_callback,
        )
        if event_callback is not None:
            d.event_callback = event_callback
        return d

    # 鈹€鈹€ TOOL_START 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def test_tool_use_emits_tool_start_event(self):
        """ToolUseBlock 瑙﹀彂 TOOL_START 浜嬩欢銆?""
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
        """TOOL_START 浜嬩欢鐨?input_summary 鍖呭惈鍏抽敭鍙傛暟銆?""
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

    # 鈹€鈹€ TOOL_RESULT 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def test_tool_result_emits_tool_result_event(self):
        """ToolResultBlock 瑙﹀彂 TOOL_RESULT 浜嬩欢銆?""
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
        """閿欒宸ュ叿缁撴灉 is_error=True銆?""
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

    # 鈹€鈹€ THINKING 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def test_thinking_block_emits_thinking_event(self):
        """ThinkingBlock 瑙﹀彂 THINKING 浜嬩欢銆?""
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
        """闀挎€濊€冩枃鏈殑 preview 鑷姩鎴柇銆?""
        events: list[PipelineEvent] = []
        d = self._make_dispatcher(event_callback=events.append)

        long_text = "x" * 200
        block = ThinkingBlock(thinking=long_text, signature="s")
        d._handle_assistant(_make_assistant_message(block))

        think = [e for e in events
                 if e.event_type == EventType.THINKING][0]
        assert think.data.preview is not None
        assert len(think.data.preview) <= 100

    # 鈹€鈹€ PROGRESS 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def test_task_progress_emits_progress_event(self):
        """TaskProgressMessage 瑙﹀彂 PROGRESS 浜嬩欢銆?""
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

    # 鈹€鈹€ 鍚戝悗鍏煎 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def test_log_callback_still_works_without_event_callback(self):
        """涓嶈缃?event_callback 鏃讹紝log_callback 姝ｅ父宸ヤ綔銆?""
        logs: list[str] = []
        d = self._make_dispatcher(log_callback=logs.append)

        block = ToolUseBlock(
            id="tu_1", name="Read",
            input={"file_path": "config.json"},
        )
        d._handle_assistant(_make_assistant_message(block))
        assert len(logs) > 0  # 鑷冲皯鏈夊伐鍏疯皟鐢ㄦ棩蹇楄

    def test_no_crash_when_event_callback_is_none(self):
        """event_callback 涓?None 鏃朵笉宕╂簝锛堥粯璁よ涓猴級銆?""
        d = self._make_dispatcher()  # 鏃犲洖璋?
        block = ToolUseBlock(id="tu_1", name="Write", input={})
        # 涓嶅簲鎶涘紓甯?
        d._handle_assistant(_make_assistant_message(block))

    def test_both_callbacks_fire_together(self):
        """log_callback 鍜?event_callback 鍚屾椂瑙﹀彂銆?""
        logs: list[str] = []
        events: list[PipelineEvent] = []
        d = self._make_dispatcher(
            log_callback=logs.append,
            event_callback=events.append,
        )

        block = ThinkingBlock(thinking="hello", signature="s")
        d._handle_assistant(_make_assistant_message(block))

        assert len(logs) > 0  # 鏂囨湰鏃ュ織
        assert any(e.event_type == EventType.THINKING
                   for e in events)  # 缁撴瀯鍖栦簨浠?


# 鈹€鈹€ Phase 7: StreamEvent 澶勭悊 (绾㈢伅) 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€


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



