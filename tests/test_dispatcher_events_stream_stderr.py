from claude_agent_sdk import StreamEvent, TaskProgressMessage, TaskUsage, ThinkingBlock, ToolResultBlock, ToolUseBlock

from manim_agent.pipeline_events import EventType

from ._test_main_dispatcher_helpers import _MessageDispatcher, _make_assistant_message


class TestDispatcherStructuredEvents:
    def test_tool_use_emits_tool_start_event(self):
        events = []
        dispatcher = _MessageDispatcher(verbose=False)
        dispatcher.event_callback = events.append

        dispatcher.dispatch(
            _make_assistant_message(
                ToolUseBlock(
                    id="tu_001",
                    name="Write",
                    input={"file_path": "scene.py", "content": "print('hello')"},
                )
            )
        )

        event = [item for item in events if item.event_type == EventType.TOOL_START][0]
        assert event.data.tool_use_id == "tu_001"
        assert event.data.name == "Write"
        assert event.data.input_summary["file_path"] == "scene.py"

    def test_tool_result_emits_tool_result_event(self):
        events = []
        dispatcher = _MessageDispatcher(verbose=False)
        dispatcher.event_callback = events.append

        dispatcher.dispatch(
            _make_assistant_message(
                ToolResultBlock(
                    tool_use_id="tu_002",
                    content="Rendered in 8.5s",
                    is_error=False,
                )
            )
        )

        event = [item for item in events if item.event_type == EventType.TOOL_RESULT][0]
        assert event.data.tool_use_id == "tu_002"
        assert event.data.is_error is False
        assert event.data.content == "Rendered in 8.5s"

    def test_thinking_emits_thinking_event(self):
        events = []
        dispatcher = _MessageDispatcher(verbose=False)
        dispatcher.event_callback = events.append

        dispatcher.dispatch(
            _make_assistant_message(
                ThinkingBlock(
                    thinking="I should animate the transform first.",
                    signature="sig-1",
                )
            )
        )

        event = [item for item in events if item.event_type == EventType.THINKING][0]
        assert "animate the transform" in event.data.thinking
        assert event.data.signature == "sig-1"

    def test_task_progress_emits_progress_event(self):
        events = []
        dispatcher = _MessageDispatcher(verbose=False)
        dispatcher.event_callback = events.append

        dispatcher.dispatch(
            TaskProgressMessage(
                subtype="task_progress",
                task_id="task-1",
                description="rendering",
                usage=TaskUsage(total_tokens=5000, tool_uses=3, duration_ms=10000),
                uuid="u1",
                session_id="s1",
                data={},
            )
        )

        event = [item for item in events if item.event_type == EventType.PROGRESS][0]
        assert event.data.turn == 1
        assert event.data.total_tokens == 5000
        assert event.data.tool_uses == 3
        assert event.data.elapsed_ms == 10000

    def test_log_callback_and_event_callback_can_work_together(self):
        logs = []
        events = []
        dispatcher = _MessageDispatcher(verbose=False, log_callback=logs.append)
        dispatcher.event_callback = events.append

        dispatcher.dispatch(
            TaskProgressMessage(
                subtype="task_progress",
                task_id="task-1",
                description="rendering",
                usage=TaskUsage(total_tokens=5000, tool_uses=3, duration_ms=10000),
                uuid="u1",
                session_id="s1",
                data={},
            )
        )

        assert logs
        assert any(item.event_type == EventType.PROGRESS for item in events)

    def test_tool_use_does_not_duplicate_into_plain_logs(self):
        logs = []
        events = []
        dispatcher = _MessageDispatcher(verbose=False, log_callback=logs.append)
        dispatcher.event_callback = events.append

        dispatcher.dispatch(
            _make_assistant_message(
                ToolUseBlock(id="tu_003", name="Read", input={"file_path": "scene.py"})
            )
        )

        assert not logs
        assert any(item.event_type == EventType.TOOL_START for item in events)

    def test_thinking_does_not_duplicate_into_plain_logs(self):
        logs = []
        events = []
        dispatcher = _MessageDispatcher(verbose=False, log_callback=logs.append)
        dispatcher.event_callback = events.append

        dispatcher.dispatch(
            _make_assistant_message(
                ThinkingBlock(
                    thinking="I should animate the transform first.",
                    signature="sig-1",
                )
            )
        )

        assert not logs
        assert any(item.event_type == EventType.THINKING for item in events)


class TestDispatcherStreamEventHandling:
    @staticmethod
    def _make_stream_event(event_data):
        return StreamEvent(
            uuid="stream-1",
            session_id="session-1",
            event=event_data,
        )

    def test_text_delta_stream_event_is_logged(self):
        logs = []
        dispatcher = _MessageDispatcher(verbose=False, log_callback=logs.append)

        dispatcher.dispatch(
            self._make_stream_event(
                {
                    "type": "content_block_delta",
                    "delta": {"type": "text_delta", "text": "partial output"},
                }
            )
        )

        assert any("[STREAM]" in line and "partial output" in line for line in logs)

    def test_thinking_delta_stream_event_is_logged(self):
        logs = []
        dispatcher = _MessageDispatcher(verbose=False, log_callback=logs.append)

        dispatcher.dispatch(
            self._make_stream_event(
                {
                    "type": "content_block_delta",
                    "delta": {"type": "thinking_delta", "thinking": "step by step"},
                }
            )
        )

        assert any("[THINK-DELTA]" in line and "step by step" in line for line in logs)

    def test_stream_event_without_callback_does_not_crash(self):
        dispatcher = _MessageDispatcher(verbose=False)
        dispatcher.dispatch(self._make_stream_event({"type": "message_start"}))
