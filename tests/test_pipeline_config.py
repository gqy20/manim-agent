"""Tests for pipeline_config module (SDK options + path helpers + emit_status)."""

import inspect


class TestBuildOptions:
    def test_phase1_tool_isolation_options_are_forwarded(self, tmp_path):
        from manim_agent.pipeline_config import build_options

        options = build_options(
            cwd=str(tmp_path),
            system_prompt="planning",
            max_turns=8,
            use_default_output_format=False,
            tools=[],
            allowed_tools=[],
            disallowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
            skills=[],
        )

        assert options.tools == []
        assert options.allowed_tools == []
        assert options.disallowed_tools == ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]
        assert options.skills == []

    def test_phase1_tool_isolation_matches_sdk_cli_contract(self, tmp_path):
        from claude_agent_sdk._internal.transport.subprocess_cli import SubprocessCLITransport

        from manim_agent.pipeline_config import build_options
        from manim_agent.schemas import PhaseSchemaRegistry

        options = build_options(
            cwd=str(tmp_path),
            system_prompt="planning",
            max_turns=8,
            output_format=PhaseSchemaRegistry.output_format_schema("phase1_planning"),
            use_default_output_format=False,
            tools=[],
            allowed_tools=[],
            disallowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
            skills=[],
        )
        transport = SubprocessCLITransport(prompt="test", options=options)
        transport._cli_path = "claude"

        cmd = transport._build_command()

        assert cmd[cmd.index("--tools") + 1] == ""
        assert "--allowedTools" not in cmd
        assert cmd[cmd.index("--disallowedTools") + 1] == "Read,Write,Edit,Bash,Glob,Grep"
        assert "--json-schema" in cmd


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
        from manim_agent.pipeline_events import EventType, PipelineEvent

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
