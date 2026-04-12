from claude_agent_sdk import RateLimitEvent, RateLimitInfo, TaskNotificationMessage, TaskProgressMessage, TaskUsage

from ._test_main_dispatcher_helpers import (
    _MessageDispatcher,
    _make_assistant_message,
    _make_result_message,
    _make_text_block,
    _make_thinking_block,
    _make_tool_result_block,
    _make_tool_use_block,
)


class TestMessageDispatcherState:
    def test_default_state(self):
        dispatcher = _MessageDispatcher(verbose=False)

        assert dispatcher.verbose is False
        assert dispatcher.turn_count == 0
        assert dispatcher.tool_use_count == 0
        assert dispatcher.collected_text == []
        assert dispatcher.video_output is None
        assert dispatcher.result_summary is None

    def test_dispatch_collects_text_and_tool_count(self):
        dispatcher = _MessageDispatcher(verbose=False)

        dispatcher.dispatch(
            _make_assistant_message(
                _make_text_block("hello"),
                _make_tool_use_block("Bash", {"command": "manim -qh scene.py GeneratedScene"}),
                _make_text_block("world"),
            )
        )

        assert dispatcher.collected_text == ["hello", "world"]
        assert dispatcher.tool_use_count == 1
        assert dispatcher.tool_stats == {"Bash": 1}

    def test_dispatch_accepts_tool_result_and_thinking_blocks(self):
        dispatcher = _MessageDispatcher(verbose=False)

        dispatcher.dispatch(
            _make_assistant_message(
                _make_tool_result_block(content="ok"),
                _make_thinking_block("plan the animation"),
            )
        )

        assert dispatcher.tool_use_count == 0
        assert dispatcher.collected_text == []

    def test_result_message_populates_summary(self):
        dispatcher = _MessageDispatcher(verbose=False)

        dispatcher.dispatch(
            _make_result_message(
                num_turns=5,
                total_cost_usd=0.056,
                is_error=True,
                errors=["timeout"],
            )
        )

        assert dispatcher.result_summary == {
            "turns": 5,
            "cost_usd": 0.056,
            "duration_ms": 5000,
            "is_error": True,
            "stop_reason": "end_turn",
            "errors": ["timeout"],
        }

    def test_rate_limit_event_is_handled(self):
        dispatcher = _MessageDispatcher(verbose=False)

        dispatcher.dispatch(
            RateLimitEvent(
                rate_limit_info=RateLimitInfo(status="allowed_warning", utilization=0.75),
                uuid="u1",
                session_id="s1",
            )
        )

        assert dispatcher.result_summary is None

    def test_task_progress_increments_turn_count(self):
        dispatcher = _MessageDispatcher(verbose=False)

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

        assert dispatcher.turn_count == 1

    def test_completed_task_notification_sets_video_output(self):
        dispatcher = _MessageDispatcher(verbose=False)

        dispatcher.dispatch(
            TaskNotificationMessage(
                subtype="task_notification",
                task_id="task-1",
                status="completed",
                output_file="/out/video.mp4",
                summary="done",
                uuid="u1",
                session_id="s1",
                data={},
            )
        )

        assert dispatcher.video_output is not None
        assert dispatcher.video_output.endswith("video.mp4")
        assert dispatcher.task_notification_status == "completed"

    def test_unknown_message_type_is_ignored(self):
        class FakeMessage:
            pass

        dispatcher = _MessageDispatcher(verbose=False)
        dispatcher.dispatch(FakeMessage())  # type: ignore[arg-type]

        assert dispatcher.tool_use_count == 0
