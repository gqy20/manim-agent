from ._test_main_dispatcher_helpers import *

class TestStructuredOutput:
    """楠岃瘉 SDK structured_output 涓昏矾寰勩€?""

    def test_handle_result_parses_structured_output(self):
        """ResultMessage 鐨?structured_output 琚В鏋愪负 PipelineOutput銆?""
        d = _MessageDispatcher(verbose=False)
        msg = _make_result_message(
            num_turns=2,
            **{"structured_output": {
                "video_output": "/structured/out.mp4",
                "scene_file": "s.py",
                "scene_class": "SScene",
                "duration_seconds": 15,
                "narration": "缁撴瀯鍖栬В璇?,
            }},
        )
        d.dispatch(msg)

        po = d.get_pipeline_output()
        assert po is not None
        assert po.video_output == "/structured/out.mp4"
        assert po.narration == "缁撴瀯鍖栬В璇?

    def test_handle_result_null_structured_output_returns_none(self):
        """structured_output=None 鏃?get_pipeline_output() 杩斿洖 None銆?""
        d = _MessageDispatcher(verbose=False)
        msg = _make_result_message(
            num_turns=1,
            **{"structured_output": None},
        )
        d.dispatch(msg)
        assert d.get_pipeline_output() is None

    def test_handle_result_structured_output_as_json_string(self):
        """SDK 杩斿洖 JSON 瀛楃涓叉牸寮忕殑 structured_output 鏃舵纭В鏋愩€?

        鏌愪簺 CLI 鐗堟湰灏?structured_output 浣滀负 JSON 瀛楃涓茶繑鍥?
        鑰岄潪宸茶В鏋愮殑 dict锛宒ispatcher 搴旇兘澶勭悊姝ゆ儏鍐点€?
        """
        d = _MessageDispatcher(verbose=False)
        msg = _make_result_message(
            num_turns=2,
            **{"structured_output": json.dumps({
                "video_output": "/string/out.mp4",
                "scene_file": "s.py",
                "scene_class": "SScene",
                "duration_seconds": 15,
                "narration": "瀛楃涓叉牸寮忚В璇?,
            })},
        )
        d.dispatch(msg)

        po = d.get_pipeline_output()
        assert po is not None
        assert po.video_output == "/string/out.mp4"
        assert po.scene_file == "s.py"
        assert po.narration == "瀛楃涓叉牸寮忚В璇?


class TestBuildOptionsOutputFormat:
    """楠岃瘉 _build_options 鍖呭惈 output_format schema銆?""

    def test_options_include_output_format(self):
        """_build_options() 杩斿洖鐨?options 鍚?output_format 瀛楁銆?""
        opts = main_module._build_options(
            cwd="/work",
            system_prompt="test",
            max_turns=10,
        )
        assert opts.output_format is not None
        assert opts.output_format["type"] == "json_schema"

    def test_output_format_schema_has_required_fields(self):
        """schema 瑕佹眰 video_output 蹇呭～锛屽叾浣欏彲閫夈€?""
        opts = main_module._build_options(
            cwd="/work",
            system_prompt="test",
            max_turns=10,
        )
        schema = opts.output_format["json_schema"]["schema"]
        assert "video_output" in schema["required"]
        assert "narration" in schema["properties"]


# 鈹€鈹€ Phase B: Dispatcher 缁撴瀯鍖栦簨浠跺彂灏?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€


from manim_agent.pipeline_events import (
    EventType,
    PipelineEvent,
    ToolStartPayload,
    ToolResultPayload,
    ThinkingPayload,
    ProgressPayload,
)


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



