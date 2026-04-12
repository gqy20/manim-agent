import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from manim_agent.repo_paths import resolve_plugin_dir

from ._test_main_dispatcher_helpers import (
    _make_assistant_message,
    _make_result_message,
    _make_text_block,
    _make_tool_use_block,
    main_module,
)


_SCENE_PLAN_TEXT = """## Mode
quick-demo
## Learning Goal
Show one clean transformation.
## Audience
General learners.
## Beat List
1. Introduce the circle.
2. Transform it into a square.
## Narration Outline
Describe the change clearly.
## Visual Risks
Avoid crowding.
## Build Handoff
Implement in one focused scene.
"""


def _planning_messages():
    return [
        _make_assistant_message(_make_text_block(_SCENE_PLAN_TEXT)),
        _make_result_message(num_turns=1, total_cost_usd=0.001),
    ]


def _make_staged_query(build_messages):
    call_count = {"value": 0}

    async def _query(*args, **kwargs):
        call_count["value"] += 1
        messages = _planning_messages() if call_count["value"] == 1 else build_messages
        for msg in messages:
            yield msg

    return _query


def _approved_review_result():
    return MagicMock(
        summary="Layout and framing look good.",
        approved=True,
        blocking_issues=[],
        suggested_edits=[],
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
    async def test_full_flow_with_tts(self, tmp_path):
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
            patch("manim_agent.__main__.render_review.extract_review_frames", new_callable=AsyncMock, return_value=[]),
            patch("manim_agent.__main__._run_render_review", new_callable=AsyncMock, return_value=_approved_review_result()),
            patch("manim_agent.__main__.tts_client.synthesize", new_callable=AsyncMock) as mock_tts,
            patch("manim_agent.__main__.video_builder.build_final_video", new_callable=AsyncMock) as mock_video,
        ):
            mock_query.side_effect = _make_staged_query(mock_messages)
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
                cwd=str(tmp_path),
            )

            assert result == "output/final.mp4"
            mock_tts.assert_awaited_once()
            mock_video.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skip_tts_mode(self, tmp_path):
        mock_messages = [
            _make_assistant_message(_make_text_block("render complete")),
            _make_result_message(
                num_turns=1,
                **{"structured_output": {"video_output": "media/silent.mp4"}},
            ),
        ]

        with (
            patch("manim_agent.__main__.query") as mock_query,
            patch("manim_agent.__main__.render_review.extract_review_frames", new_callable=AsyncMock, return_value=[]),
            patch("manim_agent.__main__._run_render_review", new_callable=AsyncMock, return_value=_approved_review_result()),
            patch("manim_agent.__main__.tts_client.synthesize", new_callable=AsyncMock) as mock_tts,
            patch("manim_agent.__main__.video_builder.build_final_video", new_callable=AsyncMock) as mock_video,
        ):
            mock_query.side_effect = _make_staged_query(mock_messages)

            result = await main_module.run_pipeline(
                user_text="测试",
                output_path="output/out.mp4",
                no_tts=True,
                cwd=str(tmp_path),
            )

            assert result == str(Path("media/silent.mp4").resolve())
            mock_tts.assert_not_awaited()
            mock_video.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_tts_emits_authoritative_status_phases(self, tmp_path):
        from manim_agent.pipeline_events import EventType

        events = []
        mock_messages = [
            _make_assistant_message(_make_text_block("render complete")),
            _make_result_message(
                num_turns=1,
                **{"structured_output": {"video_output": "media/silent.mp4"}},
            ),
        ]

        with (
            patch("manim_agent.__main__.query") as mock_query,
            patch("manim_agent.__main__.render_review.extract_review_frames", new_callable=AsyncMock, return_value=[]),
            patch("manim_agent.__main__._run_render_review", new_callable=AsyncMock, return_value=_approved_review_result()),
        ):
            mock_query.side_effect = _make_staged_query(mock_messages)

            result = await main_module.run_pipeline(
                user_text="test",
                output_path="output/out.mp4",
                no_tts=True,
                event_callback=events.append,
                cwd=str(tmp_path),
            )

        assert result == str(Path("media/silent.mp4").resolve())
        status_events = [e for e in events if e.event_type == EventType.STATUS]
        assert [e.data.phase for e in status_events] == [
            "init",
            "scene",
            "render",
            "render",
            "render",
        ]
        assert all(e.data.task_status == "running" for e in status_events)

    @pytest.mark.asyncio
    async def test_no_video_output_raises(self, tmp_path):
        mock_messages = [
            _make_assistant_message(_make_text_block("completed without an output path")),
        ]

        with (
            patch("manim_agent.__main__.query") as mock_query,
            pytest.raises(RuntimeError, match="valid pipeline output"),
        ):
            mock_query.side_effect = _make_staged_query(mock_messages)

            await main_module.run_pipeline(
                user_text="测试",
                output_path="output/out.mp4",
                no_tts=True,
                cwd=str(tmp_path),
            )

    @pytest.mark.asyncio
    async def test_failure_before_video_output_stops_status_phase_progression(self, tmp_path):
        from manim_agent.pipeline_events import EventType

        events = []
        mock_messages = [
            _make_assistant_message(_make_text_block("no markers here")),
        ]

        with (
            patch("manim_agent.__main__.query") as mock_query,
            pytest.raises(RuntimeError, match="valid pipeline output"),
        ):
            mock_query.side_effect = _make_staged_query(mock_messages)

            await main_module.run_pipeline(
                user_text="test",
                output_path="output/out.mp4",
                no_tts=True,
                event_callback=events.append,
                cwd=str(tmp_path),
            )

        status_events = [e for e in events if e.event_type == EventType.STATUS]
        assert [e.data.phase for e in status_events] == ["init", "scene", "render"]
        assert all(e.data.task_status == "running" for e in status_events)

    @pytest.mark.asyncio
    async def test_full_flow_emits_authoritative_status_phases_in_order(self, tmp_path):
        from manim_agent.pipeline_events import EventType

        events = []
        mock_messages = [
            _make_assistant_message(_make_text_block("render complete")),
            _make_result_message(
                num_turns=1,
                **{
                    "structured_output": {
                        "video_output": "media/out.mp4",
                        "narration": "这是用于主流程测试的中文解说。",
                    }
                },
            ),
        ]

        with (
            patch("manim_agent.__main__.query") as mock_query,
            patch("manim_agent.__main__.render_review.extract_review_frames", new_callable=AsyncMock, return_value=[]),
            patch("manim_agent.__main__._run_render_review", new_callable=AsyncMock, return_value=_approved_review_result()),
            patch("manim_agent.__main__.tts_client.synthesize", new_callable=AsyncMock) as mock_tts,
            patch("manim_agent.__main__.video_builder.build_final_video", new_callable=AsyncMock) as mock_video,
        ):
            mock_query.side_effect = _make_staged_query(mock_messages)
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
                cwd=str(tmp_path),
            )

        assert result == "output/final.mp4"
        status_events = [e for e in events if e.event_type == EventType.STATUS]
        assert [e.data.phase for e in status_events] == [
            "init",
            "scene",
            "render",
            "render",
            "tts",
            "mux",
        ]
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
        assert opts.plugins is not None
        assert any(plugin["path"].endswith("plugins\\manim-production") for plugin in opts.plugins)

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

    def test_local_plugin_manifest_exists(self):
        plugin_root = resolve_plugin_dir()
        manifest = plugin_root / ".codex-plugin" / "plugin.json"
        assert plugin_root.exists()
        assert manifest.exists()

    def test_scene_plan_and_build_skills_exist(self):
        plugin_root = resolve_plugin_dir()
        scene_plan_skill = plugin_root / "skills" / "scene-plan" / "SKILL.md"
        scene_build_skill = plugin_root / "skills" / "scene-build" / "SKILL.md"
        layout_safety_skill = plugin_root / "skills" / "layout-safety" / "SKILL.md"
        layout_safety_script = (
            plugin_root / "skills" / "layout-safety" / "scripts" / "layout_safety.py"
        )
        assert scene_plan_skill.exists()
        assert scene_build_skill.exists()
        assert layout_safety_skill.exists()
        assert layout_safety_script.exists()

    def test_old_misspelled_skill_paths_do_not_exist(self):
        plugin_root = resolve_plugin_dir()
        assert not (plugin_root / "skills" / "scence-plan").exists()
        assert not (plugin_root / "skills" / "scence-build").exists()

    def test_plugin_manifest_mentions_scene_plan_and_build(self):
        manifest = resolve_plugin_dir() / ".codex-plugin" / "plugin.json"
        text = manifest.read_text(encoding="utf-8")
        assert "/scene-plan" in text
        assert "/scene-build" in text
        assert "/layout-safety" in text


class TestAsyncioImport:
    def test_asyncio_in_module_globals(self):
        assert hasattr(main_module, "asyncio")

    def test_main_is_coroutine_function(self):
        import inspect

        assert inspect.iscoroutinefunction(main_module.main)

    def test_main_callable_without_nameerror(self):
        assert callable(main_module.main)


class TestBackgroundMusic:
    @pytest.mark.asyncio
    async def test_bgm_failure_falls_back_to_voice_only_mux(self, tmp_path):
        mock_messages = [
            _make_assistant_message(_make_text_block("render complete")),
            _make_result_message(
                num_turns=1,
                **{
                    "structured_output": {
                        "video_output": "media/out.mp4",
                        "narration": "Fallback-safe narration for the BGM error path.",
                    }
                },
            ),
        ]

        with (
            patch("manim_agent.__main__.query") as mock_query,
            patch("manim_agent.__main__.render_review.extract_review_frames", new_callable=AsyncMock, return_value=[]),
            patch("manim_agent.__main__._run_render_review", new_callable=AsyncMock, return_value=_approved_review_result()),
            patch("manim_agent.__main__.tts_client.synthesize", new_callable=AsyncMock) as mock_tts,
            patch(
                "manim_agent.__main__.music_client.generate_instrumental",
                new_callable=AsyncMock,
                side_effect=RuntimeError("bgm unavailable"),
            ) as mock_bgm,
            patch("manim_agent.__main__.video_builder.build_final_video", new_callable=AsyncMock) as mock_video,
        ):
            mock_query.side_effect = _make_staged_query(mock_messages)
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
                bgm_enabled=True,
                cwd=str(tmp_path),
            )

        assert result == "output/final.mp4"
        mock_tts.assert_awaited_once()
        mock_bgm.assert_awaited_once()
        mock_video.assert_awaited_once_with(
            video_path=str(Path("media/out.mp4").resolve()),
            audio_path="out/audio.mp3",
            subtitle_path="out/sub.srt",
            output_path="output/final.mp4",
            bgm_path=None,
            bgm_volume=0.12,
        )
