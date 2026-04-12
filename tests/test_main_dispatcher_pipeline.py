import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ._test_main_dispatcher_helpers import (
    _make_assistant_message,
    _make_result_message,
    _make_text_block,
    _make_tool_use_block,
    main_module,
)


class TestSessionIsolation:
    def test_unique_session_id_per_call(self):
        id1 = str(uuid.uuid4())
        id2 = str(uuid.uuid4())
        assert id1 != id2
        assert len(id1) == 36

    def test_build_options_includes_session_fields(self):
        options = main_module._build_options(
            cwd="/project",
            system_prompt="test prompt",
            max_turns=10,
        )
        assert hasattr(options, "session_id")
        assert hasattr(options, "fork_session")
        assert options.session_id is not None
        assert options.fork_session is True

    def test_fork_session_always_true(self):
        options = main_module._build_options(
            cwd="/project",
            system_prompt="test",
            max_turns=5,
        )
        assert options.fork_session is True


class TestRunPipeline:
    @pytest.mark.asyncio
    async def test_full_flow_with_tts(self):
        mock_messages = [
            _make_assistant_message(
                _make_text_block("render complete"),
                _make_tool_use_block("Write", {"file_path": "scene.py"}),
            ),
            _make_result_message(
                num_turns=2,
                total_cost_usd=0.02,
                **{
                    "structured_output": {
                        "video_output": "media/out.mp4",
                        "scene_file": "scene.py",
                        "scene_class": "GeneratedScene",
                        "narration": "这是一个圆形变成正方形的中文讲解。",
                    }
                },
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
            mock_tts.return_value = MagicMock(
                audio_path="out/audio.mp3",
                subtitle_path="out/sub.srt",
                duration_ms=30000,
            )
            mock_video.return_value = "output/final.mp4"

            result = await main_module.run_pipeline(
                user_text="做一个圆形变成正方形的动画，并用中文配音讲解",
                output_path="output/final.mp4",
                voice_id="female-tianmei",
                no_tts=False,
            )

            assert result == "output/final.mp4"
            mock_tts.assert_awaited_once()
            mock_video.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skip_tts_mode(self):
        mock_messages = [
            _make_assistant_message(_make_text_block("render complete")),
            _make_result_message(
                num_turns=1,
                **{"structured_output": {"video_output": "media/silent.mp4"}},
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
                user_text="测试",
                output_path="output/out.mp4",
                no_tts=True,
            )

            assert result == str(Path("media/silent.mp4").resolve())
            mock_tts.assert_not_awaited()
            mock_video.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_tts_emits_authoritative_status_phases(self):
        from manim_agent.pipeline_events import EventType

        events = []
        mock_messages = [
            _make_assistant_message(_make_text_block("render complete")),
            _make_result_message(
                num_turns=1,
                **{"structured_output": {"video_output": "media/silent.mp4"}},
            ),
        ]

        with patch("manim_agent.__main__.query") as mock_query:
            async def mock_query_gen(*args, **kwargs):
                for msg in mock_messages:
                    yield msg

            mock_query.side_effect = mock_query_gen

            result = await main_module.run_pipeline(
                user_text="test",
                output_path="output/out.mp4",
                no_tts=True,
                event_callback=events.append,
            )

        assert result == str(Path("media/silent.mp4").resolve())
        status_events = [e for e in events if e.event_type == EventType.STATUS]
        assert [e.data.phase for e in status_events] == ["init", "render", "render"]
        assert all(e.data.task_status == "running" for e in status_events)

    @pytest.mark.asyncio
    async def test_no_video_output_raises(self):
        mock_messages = [
            _make_assistant_message(_make_text_block("completed without an output path")),
        ]

        with (
            patch("manim_agent.__main__.query") as mock_query,
            pytest.raises(RuntimeError, match="valid pipeline output"),
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

    @pytest.mark.asyncio
    async def test_failure_before_video_output_stops_status_phase_progression(self):
        from manim_agent.pipeline_events import EventType

        events = []
        mock_messages = [
            _make_assistant_message(_make_text_block("no markers here")),
        ]

        with (
            patch("manim_agent.__main__.query") as mock_query,
            pytest.raises(RuntimeError, match="valid pipeline output"),
        ):
            async def mock_query_gen(*args, **kwargs):
                for msg in mock_messages:
                    yield msg

            mock_query.side_effect = mock_query_gen

            await main_module.run_pipeline(
                user_text="test",
                output_path="output/out.mp4",
                no_tts=True,
                event_callback=events.append,
            )

        status_events = [e for e in events if e.event_type == EventType.STATUS]
        assert [e.data.phase for e in status_events] == ["init", "render"]
        assert all(e.data.task_status == "running" for e in status_events)

    @pytest.mark.asyncio
    async def test_full_flow_emits_authoritative_status_phases_in_order(self):
        from manim_agent.pipeline_events import EventType

        events = []
        mock_messages = [
            _make_assistant_message(_make_text_block("render complete")),
            _make_result_message(
                num_turns=1,
                **{"structured_output": {"video_output": "media/out.mp4"}},
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
            mock_tts.return_value = MagicMock(
                audio_path="out/audio.mp3",
                subtitle_path="out/sub.srt",
                duration_ms=30000,
                word_count=128,
            )
            mock_video.return_value = "output/final.mp4"

            result = await main_module.run_pipeline(
                user_text="test content",
                output_path="output/final.mp4",
                no_tts=False,
                event_callback=events.append,
            )

        assert result == "output/final.mp4"
        status_events = [e for e in events if e.event_type == EventType.STATUS]
        assert [e.data.phase for e in status_events] == ["init", "render", "tts", "mux"]
        assert all(e.data.task_status == "running" for e in status_events)


class TestBuildOptions:
    def test_basic_options(self):
        opts = main_module._build_options(
            cwd="/work",
            system_prompt="You are a helpful assistant.",
            max_turns=30,
        )
        assert opts.cwd == str(Path("/work").resolve())
        assert opts.system_prompt == "You are a helpful assistant."
        assert opts.max_turns == 30
        assert opts.permission_mode == "bypassPermissions"
        assert opts.allowed_tools is not None
        assert set(opts.allowed_tools) == {
            "Read",
            "Write",
            "Edit",
            "Bash",
            "Glob",
            "Grep",
        }
        assert opts.add_dirs == [str(Path("/work").resolve())]

    def test_custom_prompt_file(self, tmp_path):
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
        opts = main_module._build_options(
            cwd="/work",
            system_prompt="test",
            max_turns=5,
        )
        assert opts.stderr is not None


class TestAsyncioImport:
    def test_asyncio_in_module_globals(self):
        assert hasattr(main_module, "asyncio")

    def test_main_is_coroutine_function(self):
        import inspect

        assert inspect.iscoroutinefunction(main_module.main)

    def test_main_callable_without_nameerror(self):
        assert callable(main_module.main)
