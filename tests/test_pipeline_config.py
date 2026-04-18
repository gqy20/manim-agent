"""Tests for pipeline_config module (SDK options + path helpers + emit_status)."""

import inspect
from unittest.mock import MagicMock

import pytest


class TestPipelineConfigExports:
    """Verify pipeline_config re-exports the functions expected by pipeline.py."""

    def test_build_options_exported(self):
        from manim_agent.pipeline_config import build_options

        assert callable(build_options)

    def test_stderr_handler_exported(self):
        from manim_agent.pipeline_config import stderr_handler

        assert callable(stderr_handler)

    def test_emit_status_exported(self):
        from manim_agent.pipeline_config import emit_status

        assert callable(emit_status)

    def test_resolve_repo_root_exported(self):
        from manim_agent.pipeline_config import resolve_repo_root

        assert callable(resolve_repo_root)

    def test_resolve_plugin_dir_exported(self):
        from manim_agent.pipeline_config import resolve_plugin_dir

        assert callable(resolve_plugin_dir)


class TestStderrHandler:
    """Tests for stderr_handler."""

    def test_accepts_callback(self):
        from manim_agent.pipeline_config import stderr_handler

        sig = inspect.signature(stderr_handler)
        assert "log_callback" in sig.parameters

    def test_forwards_all_lines(self):
        from manim_agent.pipeline_config import stderr_handler

        lines = [
            "Error: connection refused",
            "Warning: rate limit approaching",
            "Using model claude-sonnet-4-20250514",
        ]
        forwarded = []
        for line in lines:
            stderr_handler(line, log_callback=forwarded.append)
        assert forwarded == [f"[CLI] {line}" for line in lines]

    def test_error_lines_go_to_stderr(self, capsys):
        from manim_agent.pipeline_config import stderr_handler

        stderr_handler("Error: something failed", log_callback=None)
        captured = capsys.readouterr()
        assert "Error: something failed" in captured.err

    def test_non_error_silent_on_stderr(self, capsys):
        from manim_agent.pipeline_config import stderr_handler

        stderr_handler("info: all good", log_callback=None)
        captured = capsys.readouterr()
        assert captured.err == ""


class TestEmitStatus:
    """Tests for emit_status helper."""

    def test_calls_event_callback_with_pipeline_event(self):
        from manim_agent.pipeline_config import emit_status
        from manim_agent.pipeline_events import PipelineEvent, EventType

        events = []
        cb = events.append

        emit_status(cb, task_status="running", phase="render", message="test message")

        assert len(events) == 1
        evt = events[0]
        assert isinstance(evt, PipelineEvent)
        assert evt.event_type == EventType.STATUS
        assert evt.data.task_status == "running"
        assert evt.data.phase == "render"
        assert evt.data.message == "test message"

    def test_none_callback_does_not_raise(self):
        from manim_agent.pipeline_config import emit_status

        emit_status(None, task_status="running", phase="render")

    def test_optional_fields_omitted(self):
        from manim_agent.pipeline_config import emit_status
        from manim_agent.pipeline_events import EventType

        events = []
        emit_status(events.append, task_status="running")
        evt = events[0]
        assert evt.data.phase is None
        assert evt.data.message is None


class TestPathHelpers:
    """Tests for path resolution helpers."""

    def test_resolve_repo_root_returns_path(self):
        from manim_agent.pipeline_config import resolve_repo_root

        result = resolve_repo_root(".")
        assert result is not None

    def test_resolve_plugin_dir_returns_path(self):
        from manim_agent.pipeline_config import resolve_plugin_dir

        result = resolve_plugin_dir(".")
        assert result is not None
        assert "manim-production" in str(result)
