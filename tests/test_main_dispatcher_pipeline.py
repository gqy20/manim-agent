import json
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
        _make_result_message(
            num_turns=1,
            total_cost_usd=0.001,
            structured_output={
                "build_spec": {
                    "mode": "quick-demo",
                    "learning_goal": "Show one clean transformation.",
                    "audience": "General learners.",
                    "target_duration_seconds": 60,
                    "beats": [
                        {
                            "id": "beat_001_intro_circle",
                            "title": "Introduce the circle",
                            "visual_goal": "Show the starting circle cleanly.",
                            "narration_intent": "Introduce the initial circle.",
                            "target_duration_seconds": 12,
                            "required_elements": ["circle"],
                            "segment_required": True,
                        },
                        {
                            "id": "beat_002_transform_square",
                            "title": "Transform into a square",
                            "visual_goal": "Animate the circle transforming into a square.",
                            "narration_intent": "Explain the transformation clearly.",
                            "target_duration_seconds": 18,
                            "required_elements": ["circle", "square"],
                            "segment_required": True,
                        },
                    ],
                },
            },
        ),
    ]


def _make_staged_query(build_messages):
    call_count = {"value": 0}

    async def _query(*args, **kwargs):
        call_count["value"] += 1
        if call_count["value"] == 1:
            messages = _planning_messages()
        elif call_count["value"] == 2:
            options = kwargs.get("options") if kwargs else None
            cwd = Path(getattr(options, "cwd", "."))
            source_code = """
from manim import *

class GeneratedScene(Scene):
    def construct(self):
        self.beat_001_intro_circle()
        self.beat_002_transform_square()

    def beat_001_intro_circle(self):
        self.play(FadeIn(Circle()), run_time=20)
        self.wait(1)

    def beat_002_transform_square(self):
        self.play(FadeIn(Square()), run_time=20)
        self.wait(1)
"""
            (cwd / "scene.py").write_text(
                source_code,
                encoding="utf-8",
            )
            messages = [
                _make_result_message(
                    num_turns=1,
                    total_cost_usd=0.001,
                    structured_output={
                        "scene_file": "scene.py",
                        "scene_class": "GeneratedScene",
                        "implemented_beats": [
                            "Introduce the circle",
                            "Transform into a square",
                        ],
                        "build_summary": "Built the beat-first script draft.",
                        "beat_timing_seconds": {
                            "beat_001_intro_circle": 21.0,
                            "beat_002_transform_square": 21.0,
                        },
                        "estimated_duration_seconds": 42.0,
                        "deviations_from_plan": [],
                        "source_code": source_code,
                    },
                )
            ]
        else:
            options = kwargs.get("options") if kwargs else None
            cwd = Path(getattr(options, "cwd", "."))
            for msg in build_messages:
                structured_output = getattr(msg, "structured_output", None)
                if isinstance(structured_output, dict):
                    structured_output.setdefault("scene_file", "scene.py")
                    structured_output.setdefault("scene_class", "GeneratedScene")
                    video_output = structured_output.get("video_output")
                    if isinstance(video_output, str) and video_output:
                        video_path = cwd / video_output
                        video_path.parent.mkdir(parents=True, exist_ok=True)
                        video_path.write_bytes(b"render")
                    if structured_output.get("implemented_beats") and structured_output.get(
                        "build_summary"
                    ):
                        structured_output.setdefault(
                            "narration",
                            "这是用于测试的中文解说文本，覆盖当前实现的主要动画流程。",
                        )
            messages = build_messages
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


class TestRunPipeline:
    @pytest.mark.asyncio
    async def test_phase2a_repair_uses_fresh_session_and_marks_debug_failure(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.delenv("ENABLE_PROMPT_DEBUG", raising=False)
        sessions = []
        call_count = {"value": 0}

        async def _query(*args, **kwargs):
            call_count["value"] += 1
            options = kwargs.get("options") if kwargs else None
            sessions.append(getattr(options, "session_id", None))
            cwd = Path(getattr(options, "cwd", tmp_path))
            if call_count["value"] == 1:
                messages = _planning_messages()
            elif call_count["value"] == 2:
                (cwd / "scene.py").write_text(
                    short_source := """
from manim import *

class GeneratedScene(Scene):
    def construct(self):
        self.beat_001_intro_circle()
        self.beat_002_transform_square()

    def beat_001_intro_circle(self):
        self.wait(1)

    def beat_002_transform_square(self):
        self.wait(1)
""",
                    encoding="utf-8",
                )
                messages = [
                    _make_result_message(
                        num_turns=1,
                        structured_output={
                            "scene_file": "scene.py",
                            "scene_class": "GeneratedScene",
                            "implemented_beats": [
                                "Introduce the circle",
                                "Transform into a square",
                            ],
                            "build_summary": "Draft is intentionally too short.",
                            "beat_timing_seconds": {
                                "beat_001_intro_circle": 1.0,
                                "beat_002_transform_square": 1.0,
                            },
                            "estimated_duration_seconds": 2.0,
                            "deviations_from_plan": [],
                            "source_code": short_source,
                        },
                    )
                ]
            elif call_count["value"] == 3:
                raise RuntimeError("repair boom")
            else:
                messages = []
            for msg in messages:
                yield msg

        with (
            patch("manim_agent.pipeline.query", side_effect=_query),
            pytest.raises(RuntimeError, match="repair boom"),
        ):
            await main_module.run_pipeline(
                user_text="test",
                output_path="output/out.mp4",
                no_tts=True,
                cwd=str(tmp_path),
            )

        repair_artifact = json.loads(
            (tmp_path / "debug" / "phase2a-repair.prompt.json").read_text(encoding="utf-8")
        )
        assert len(sessions) >= 3
        assert sessions[1] != sessions[2]
        assert repair_artifact["options"]["session_id"] == sessions[2]
        assert repair_artifact["status"] == "failed"
        assert "RuntimeError: repair boom" in repair_artifact["error"]
        assert "failed_analysis" in repair_artifact["output_snapshot"]

    @pytest.mark.asyncio
    async def test_phase2_rejects_missing_build_bookkeeping_before_phase3(self, tmp_path):
        mock_messages = [
            _make_assistant_message(_make_text_block("render complete")),
            _make_result_message(
                num_turns=1,
                **{
                    "structured_output": {
                        "video_output": "media/out.mp4",
                    }
                },
            ),
        ]

        with (
            patch("manim_agent.pipeline.query") as mock_query,
            patch("manim_agent.pipeline.run_phase3_render", new_callable=AsyncMock) as mock_phase3,
            pytest.raises(RuntimeError, match="Phase 2 implementation output is incomplete"),
        ):
            mock_query.side_effect = _make_staged_query(mock_messages)

            await main_module.run_pipeline(
                user_text="test content",
                output_path="output/final.mp4",
                no_tts=True,
                cwd=str(tmp_path),
            )

        mock_phase3.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_phase2_accepts_build_spec_derived_narration_bookkeeping(self, tmp_path):
        mock_messages = [
            _make_assistant_message(_make_text_block("render complete")),
            _make_result_message(
                num_turns=1,
                **{
                    "structured_output": {
                        "video_output": "media/out.mp4",
                        "implemented_beats": ["Introduce the circle", "Transform into a square"],
                        "build_summary": "Implemented the approved two-beat transformation.",
                    }
                },
            ),
        ]

        with (
            patch("manim_agent.pipeline.query") as mock_query,
            patch("manim_agent.pipeline.run_phase3_render", new_callable=AsyncMock) as mock_phase3,
        ):
            mock_query.side_effect = _make_staged_query(mock_messages)
            mock_phase3.return_value = (
                MagicMock(
                    narration="测试解说",
                    duration_seconds=30.0,
                    scene_file=None,
                    scene_class=None,
                    implemented_beats=["Introduce the circle", "Transform into a square"],
                    build_summary="Implemented the approved two-beat transformation.",
                    beat_to_narration_map=[
                        "Introduce the circle -> Introduce the initial circle.",
                        "Transform into a square -> Explain the transformation clearly.",
                    ],
                    narration_coverage_complete=True,
                    estimated_narration_duration_seconds=30.0,
                ),
                "media/out.mp4",
                [],
            )

            with (
                patch(
                    "manim_agent.pipeline.generate_narration",
                    new_callable=AsyncMock,
                    return_value="这是用于验证 build_spec 推导字段的中文解说。",
                ),
                patch(
                    "manim_agent.pipeline.video_builder.build_final_video",
                    new_callable=AsyncMock,
                    return_value="output/final.mp4",
                ),
                patch(
                    "manim_agent.pipeline.tts_client.synthesize",
                    new_callable=AsyncMock,
                    return_value=MagicMock(
                        audio_path="out/audio.mp3",
                        subtitle_path="out/sub.srt",
                        duration_ms=30000,
                    ),
                ),
                patch(
                    "manim_agent.audio_orchestrator.video_builder.concat_audios",
                    new_callable=AsyncMock,
                    return_value="out/audio_track.mp3",
                ),
            ):
                result = await main_module.run_pipeline(
                    user_text="test content",
                    output_path="output/final.mp4",
                    cwd=str(tmp_path),
                )

        assert result == "output/final.mp4"
        mock_phase3.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_phase2_discovers_real_segments_from_build_spec_when_agent_omits_paths(
        self, tmp_path
    ):
        segment_a = tmp_path / "segments" / "beat_001_intro_circle.mp4"
        segment_b = tmp_path / "segments" / "beat_002_transform_square.mp4"
        segment_a.parent.mkdir(parents=True, exist_ok=True)
        segment_a.write_bytes(b"a")
        segment_b.write_bytes(b"b")
        mock_messages = [
            _make_assistant_message(_make_text_block("segment render complete")),
            _make_result_message(
                num_turns=1,
                **{
                    "structured_output": {
                        "video_output": None,
                        "render_mode": "segments",
                        "implemented_beats": ["Introduce the circle", "Transform into a square"],
                        "build_summary": "Implemented both planned segments.",
                    }
                },
            ),
        ]

        with (
            patch("manim_agent.pipeline.query") as mock_query,
            patch("manim_agent.pipeline.run_phase3_render", new_callable=AsyncMock) as mock_phase3,
        ):
            mock_query.side_effect = _make_staged_query(mock_messages)
            mock_phase3.return_value = (
                MagicMock(
                    narration="测试解说",
                    duration_seconds=30.0,
                    scene_file=None,
                    scene_class=None,
                    implemented_beats=["Introduce the circle", "Transform into a square"],
                    build_summary="Implemented both planned segments.",
                    beat_to_narration_map=[
                        "Introduce the circle -> Introduce the initial circle.",
                        "Transform into a square -> Explain the transformation clearly.",
                    ],
                    narration_coverage_complete=True,
                    estimated_narration_duration_seconds=30.0,
                    segment_video_paths=[str(segment_a), str(segment_b)],
                    segment_render_complete=True,
                    render_mode="segments",
                ),
                str(tmp_path / "review_visual_track.mp4"),
                [],
            )

            with (
                patch(
                    "manim_agent.pipeline.generate_narration",
                    new_callable=AsyncMock,
                    return_value="这是用于验证 segments 推导字段的中文解说。",
                ),
                patch(
                    "manim_agent.pipeline.video_builder.concat_videos",
                    new_callable=AsyncMock,
                    return_value="output/segment_visual_track.mp4",
                ),
                patch(
                    "manim_agent.pipeline.video_builder.build_final_video",
                    new_callable=AsyncMock,
                    return_value="output/final.mp4",
                ),
                patch(
                    "manim_agent.pipeline.tts_client.synthesize",
                    new_callable=AsyncMock,
                    return_value=MagicMock(
                        audio_path="out/audio.mp3",
                        subtitle_path="out/sub.srt",
                        duration_ms=30000,
                    ),
                ),
                patch(
                    "manim_agent.audio_orchestrator.video_builder.concat_audios",
                    new_callable=AsyncMock,
                    return_value="out/audio_track.mp3",
                ),
            ):
                result = await main_module.run_pipeline(
                    user_text="test content",
                    output_path="output/final.mp4",
                    render_mode="segments",
                    cwd=str(tmp_path),
                )

        assert result == "output/final.mp4"
        mock_phase3.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_segments_render_mode_marks_pipeline_output_state(self, tmp_path):
        segment_a = tmp_path / "segments" / "beat_001.mp4"
        segment_b = tmp_path / "segments" / "beat_002.mp4"
        segment_a.parent.mkdir(parents=True, exist_ok=True)
        segment_a.write_bytes(b"a")
        segment_b.write_bytes(b"b")
        mock_messages = [
            _make_assistant_message(_make_text_block("render complete")),
            _make_result_message(
                num_turns=1,
                **{
                    "structured_output": {
                        "video_output": None,
                        "render_mode": "segments",
                        "segment_render_complete": True,
                        "segment_video_paths": [str(segment_a), str(segment_b)],
                        "implemented_beats": ["Opening", "Main"],
                        "build_summary": "Built two beat-level segments.",
                        "beat_to_narration_map": ["Opening -> intro", "Main -> explain"],
                        "narration_coverage_complete": True,
                        "estimated_narration_duration_seconds": 30.0,
                        "narration": "segment-aware narration",
                    }
                },
            ),
        ]
        dispatcher_refs: list[object] = []

        with (
            patch("manim_agent.pipeline.query") as mock_query,
            patch(
                "manim_agent.pipeline.render_review.extract_review_frames",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "manim_agent.pipeline._run_render_review",
                new_callable=AsyncMock,
                return_value=_approved_review_result(),
            ),
            patch("manim_agent.pipeline.tts_client.synthesize", new_callable=AsyncMock) as mock_tts,
            patch(
                "manim_agent.pipeline.video_builder.concat_videos",
                new_callable=AsyncMock,
                return_value="output/segment_visual_track.mp4",
            ),
            patch(
                "manim_agent.audio_orchestrator.video_builder.concat_audios",
                new_callable=AsyncMock,
                return_value="out/audio_track.mp3",
            ),
            patch(
                "manim_agent.pipeline.video_builder.build_final_video",
                new_callable=AsyncMock,
                return_value="output/final.mp4",
            ),
        ):
            mock_query.side_effect = _make_staged_query(mock_messages)
            mock_tts.return_value = MagicMock(
                audio_path="out/audio.mp3",
                subtitle_path="out/sub.srt",
                duration_ms=30000,
            )

            result = await main_module.run_pipeline(
                user_text="test content",
                output_path="output/final.mp4",
                no_tts=False,
                render_mode="segments",
                _dispatcher_ref=dispatcher_refs,
                cwd=str(tmp_path),
            )

        assert result == "output/final.mp4"
        dispatcher = dispatcher_refs[0]
        po = dispatcher.get_pipeline_output()
        assert po.render_mode == "segments"
        assert po.segment_render_complete is True

    @pytest.mark.asyncio
    async def test_segments_render_mode_runs_without_full_video_output(self, tmp_path):
        segment_a = tmp_path / "segments" / "beat_001.mp4"
        segment_b = tmp_path / "segments" / "beat_002.mp4"
        segment_a.parent.mkdir(parents=True, exist_ok=True)
        segment_a.write_bytes(b"a")
        segment_b.write_bytes(b"b")
        mock_messages = [
            _make_assistant_message(_make_text_block("segment render complete")),
            _make_result_message(
                num_turns=1,
                **{
                    "structured_output": {
                        "video_output": None,
                        "render_mode": "segments",
                        "segment_render_complete": True,
                        "segment_video_paths": [str(segment_a), str(segment_b)],
                        "implemented_beats": ["Opening", "Main"],
                        "build_summary": "Built two beat-level segments.",
                        "deviations_from_plan": [],
                        "beat_to_narration_map": ["Opening -> intro", "Main -> explain"],
                        "narration_coverage_complete": True,
                        "estimated_narration_duration_seconds": 30.0,
                        "run_tool_stats": {},
                        "review_blocking_issues": [],
                        "review_suggested_edits": [],
                        "review_frame_paths": [],
                        "narration": "segment-aware narration",
                    }
                },
            ),
        ]
        dispatcher_refs: list[object] = []

        with (
            patch("manim_agent.pipeline.query") as mock_query,
            patch(
                "manim_agent.pipeline.render_review.extract_review_frames",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "manim_agent.pipeline._run_render_review",
                new_callable=AsyncMock,
                return_value=_approved_review_result(),
            ),
            patch("manim_agent.pipeline.tts_client.synthesize", new_callable=AsyncMock) as mock_tts,
            patch(
                "manim_agent.pipeline.video_builder.concat_videos",
                new_callable=AsyncMock,
                return_value="output/segment_visual_track.mp4",
            ),
            patch(
                "manim_agent.audio_orchestrator.video_builder.concat_audios",
                new_callable=AsyncMock,
                return_value="out/audio_track.mp3",
            ),
            patch(
                "manim_agent.pipeline.video_builder.build_final_video",
                new_callable=AsyncMock,
                return_value="output/final.mp4",
            ) as mock_video,
        ):
            mock_query.side_effect = _make_staged_query(mock_messages)
            mock_tts.return_value = MagicMock(
                audio_path="out/audio.mp3",
                subtitle_path="out/sub.srt",
                duration_ms=30000,
            )

            result = await main_module.run_pipeline(
                user_text="test content",
                output_path="output/final.mp4",
                no_tts=False,
                render_mode="segments",
                _dispatcher_ref=dispatcher_refs,
                cwd=str(tmp_path),
            )

        assert result == "output/final.mp4"
        dispatcher = dispatcher_refs[0]
        po = dispatcher.get_pipeline_output()
        assert po.render_mode == "segments"
        assert po.segment_render_complete is True
        mock_video.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_segments_render_mode_rejects_full_render_without_real_segments(self, tmp_path):
        mock_messages = [
            _make_assistant_message(_make_text_block("render complete")),
            _make_result_message(
                num_turns=1,
                **{
                    "structured_output": {
                        "video_output": "media/out.mp4",
                        "duration_seconds": 6.0,
                        "render_mode": "segments",
                        "implemented_beats": ["Opening", "Main"],
                        "build_summary": "Built the planned beats.",
                        "deviations_from_plan": [],
                        "beat_to_narration_map": ["Opening -> intro", "Main -> explain"],
                        "narration_coverage_complete": True,
                        "estimated_narration_duration_seconds": 6.0,
                        "run_tool_stats": {},
                        "review_blocking_issues": [],
                        "review_suggested_edits": [],
                        "review_frame_paths": [],
                    }
                },
            ),
        ]
        with (
            patch("manim_agent.pipeline.query") as mock_query,
            pytest.raises(RuntimeError, match="Phase 2 implementation output is incomplete"),
        ):
            mock_query.side_effect = _make_staged_query(mock_messages)

            await main_module.run_pipeline(
                user_text="test content",
                output_path="output/final.mp4",
                no_tts=True,
                render_mode="segments",
                cwd=str(tmp_path),
            )

    @pytest.mark.asyncio
    async def test_full_flow_with_tts(self, tmp_path):
        render_path = tmp_path / "media" / "out.mp4"
        render_path.parent.mkdir(parents=True, exist_ok=True)
        render_path.write_bytes(b"render")
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
                        "implemented_beats": ["Opening", "Transformation"],
                        "build_summary": "Built the planned transformation beats.",
                        "beat_to_narration_map": [
                            "Opening -> Introduce the circle",
                            "Transformation -> Explain the square transformation",
                        ],
                        "narration_coverage_complete": True,
                        "estimated_narration_duration_seconds": 30.0,
                        "narration": "这是一个圆形变成正方形的中文讲解。",
                    }
                },
            ),
        ]

        with (
            patch("manim_agent.pipeline.query") as mock_query,
            patch(
                "manim_agent.pipeline.render_review.extract_review_frames",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "manim_agent.pipeline._run_render_review",
                new_callable=AsyncMock,
                return_value=_approved_review_result(),
            ),
            patch("manim_agent.pipeline.tts_client.synthesize", new_callable=AsyncMock) as mock_tts,
            patch(
                "manim_agent.audio_orchestrator.video_builder.concat_audios",
                new_callable=AsyncMock,
                return_value="out/audio_track.mp3",
            ),
            patch(
                "manim_agent.pipeline.video_builder.build_final_video", new_callable=AsyncMock
            ) as mock_video,
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
            assert mock_tts.await_count == 2
            mock_video.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skip_tts_mode(self, tmp_path):
        render_path = tmp_path / "media" / "silent.mp4"
        render_path.parent.mkdir(parents=True, exist_ok=True)
        render_path.write_bytes(b"render")
        mock_messages = [
            _make_assistant_message(_make_text_block("render complete")),
            _make_result_message(
                num_turns=1,
                **{
                    "structured_output": {
                        "video_output": "media/silent.mp4",
                        "implemented_beats": ["Opening", "Main"],
                        "build_summary": "Built the planned main beats.",
                        "beat_to_narration_map": ["Opening -> intro", "Main -> explain"],
                        "narration_coverage_complete": True,
                        "estimated_narration_duration_seconds": 30.0,
                    }
                },
            ),
        ]

        with (
            patch("manim_agent.pipeline.query") as mock_query,
            patch(
                "manim_agent.pipeline.render_review.extract_review_frames",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "manim_agent.pipeline._run_render_review",
                new_callable=AsyncMock,
                return_value=_approved_review_result(),
            ),
            patch("manim_agent.pipeline.tts_client.synthesize", new_callable=AsyncMock) as mock_tts,
            patch(
                "manim_agent.audio_orchestrator.video_builder.concat_audios",
                new_callable=AsyncMock,
                return_value="out/audio_track.mp3",
            ),
            patch(
                "manim_agent.pipeline.video_builder.build_final_video", new_callable=AsyncMock
            ) as mock_video,
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

        render_path = tmp_path / "media" / "silent.mp4"
        render_path.parent.mkdir(parents=True, exist_ok=True)
        render_path.write_bytes(b"render")
        events = []
        mock_messages = [
            _make_assistant_message(_make_text_block("render complete")),
            _make_result_message(
                num_turns=1,
                **{
                    "structured_output": {
                        "video_output": "media/silent.mp4",
                        "implemented_beats": ["Opening", "Main"],
                        "build_summary": "Built the planned main beats.",
                        "beat_to_narration_map": ["Opening -> intro", "Main -> explain"],
                        "narration_coverage_complete": True,
                        "estimated_narration_duration_seconds": 30.0,
                    }
                },
            ),
        ]

        with (
            patch("manim_agent.pipeline.query") as mock_query,
            patch(
                "manim_agent.pipeline.render_review.extract_review_frames",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "manim_agent.pipeline._run_render_review",
                new_callable=AsyncMock,
                return_value=_approved_review_result(),
            ),
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
            "narration",
            "render",
        ]
        assert all(e.data.task_status == "running" for e in status_events)

    @pytest.mark.asyncio
    async def test_no_video_output_raises(self, tmp_path):
        mock_messages = [
            _make_assistant_message(_make_text_block("completed without an output path")),
        ]

        with (
            patch("manim_agent.pipeline.query") as mock_query,
            pytest.raises(RuntimeError, match="Phase 2 implementation output is incomplete"),
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
            patch("manim_agent.pipeline.query") as mock_query,
            pytest.raises(RuntimeError, match="Phase 2 implementation output is incomplete"),
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
        assert [e.data.phase for e in status_events] == ["init", "scene"]
        assert all(e.data.task_status == "running" for e in status_events)

    @pytest.mark.asyncio
    async def test_full_flow_emits_authoritative_status_phases_in_order(self, tmp_path):
        from manim_agent.pipeline_events import EventType

        render_path = tmp_path / "media" / "out.mp4"
        render_path.parent.mkdir(parents=True, exist_ok=True)
        render_path.write_bytes(b"render")
        events = []
        mock_messages = [
            _make_assistant_message(_make_text_block("render complete")),
            _make_result_message(
                num_turns=1,
                **{
                    "structured_output": {
                        "video_output": "media/out.mp4",
                        "implemented_beats": ["Opening", "Main"],
                        "build_summary": "Built the planned main beats.",
                        "beat_to_narration_map": ["Opening -> intro", "Main -> explain"],
                        "narration_coverage_complete": True,
                        "estimated_narration_duration_seconds": 30.0,
                        "narration": "这是用于主流程测试的中文解说。",
                    }
                },
            ),
        ]

        with (
            patch("manim_agent.pipeline.query") as mock_query,
            patch(
                "manim_agent.pipeline.render_review.extract_review_frames",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "manim_agent.pipeline._run_render_review",
                new_callable=AsyncMock,
                return_value=_approved_review_result(),
            ),
            patch("manim_agent.pipeline.tts_client.synthesize", new_callable=AsyncMock) as mock_tts,
            patch(
                "manim_agent.audio_orchestrator.video_builder.concat_audios",
                new_callable=AsyncMock,
                return_value="out/audio_track.mp3",
            ),
            patch(
                "manim_agent.pipeline.video_builder.build_final_video", new_callable=AsyncMock
            ) as mock_video,
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
            "narration",
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
        assert str(Path("/work").resolve()) in opts.add_dirs
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


class TestBackgroundMusic:
    @pytest.mark.asyncio
    async def test_bgm_failure_falls_back_to_voice_only_mux(self, tmp_path):
        render_path = tmp_path / "media" / "out.mp4"
        render_path.parent.mkdir(parents=True, exist_ok=True)
        render_path.write_bytes(b"render")
        mock_messages = [
            _make_assistant_message(_make_text_block("render complete")),
            _make_result_message(
                num_turns=1,
                **{
                    "structured_output": {
                        "video_output": "media/out.mp4",
                        "implemented_beats": ["Opening", "Main"],
                        "build_summary": "Built the planned main beats.",
                        "beat_to_narration_map": ["Opening -> intro", "Main -> explain"],
                        "narration_coverage_complete": True,
                        "estimated_narration_duration_seconds": 30.0,
                        "narration": "Fallback-safe narration for the BGM error path.",
                    }
                },
            ),
        ]

        with (
            patch("manim_agent.pipeline.query") as mock_query,
            patch(
                "manim_agent.pipeline.render_review.extract_review_frames",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "manim_agent.pipeline._run_render_review",
                new_callable=AsyncMock,
                return_value=_approved_review_result(),
            ),
            patch("manim_agent.pipeline.tts_client.synthesize", new_callable=AsyncMock) as mock_tts,
            patch(
                "manim_agent.pipeline.music_client.generate_instrumental",
                new_callable=AsyncMock,
                side_effect=RuntimeError("bgm unavailable"),
            ) as mock_bgm,
            patch(
                "manim_agent.audio_orchestrator.video_builder.concat_audios",
                new_callable=AsyncMock,
                return_value="out/audio_track.mp3",
            ),
            patch(
                "manim_agent.pipeline.video_builder.build_final_video", new_callable=AsyncMock
            ) as mock_video,
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
        assert mock_tts.await_count == 2
        mock_bgm.assert_awaited_once()
        mock_video.assert_awaited_once_with(
            video_path=str(Path("media/out.mp4").resolve()),
            audio_path="out/audio_track.mp3",
            subtitle_path=None,
            output_path="output/final.mp4",
            bgm_path=None,
            bgm_volume=0.12,
        )
