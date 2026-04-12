from manim_agent.hooks import create_hook_state, normalize_path_string

from ._test_main_dispatcher_helpers import (
    _MessageDispatcher,
    _make_assistant_message,
    _make_result_message,
    _make_tool_use_block,
)


class TestDispatcherCodeCapture:
    def test_write_and_edit_blocks_do_not_store_code_without_hook_snapshot(self):
        dispatcher = _MessageDispatcher(verbose=False)

        dispatcher.dispatch(
            _make_assistant_message(
                _make_tool_use_block(
                    "Write",
                    {
                        "file_path": "scene.py",
                        "content": "from manim import *\nclass GeneratedScene(Scene):\n    pass",
                    },
                )
            )
        )
        dispatcher.dispatch(
            _make_assistant_message(
                _make_tool_use_block(
                    "Edit",
                    {
                        "file_path": "scene.py",
                        "content": "from manim import *\nclass GeneratedScene(Scene):\n    ...",
                    },
                    tool_id="tu_002",
                )
            )
        )

        assert dispatcher.captured_source_code == {}

    def test_pipeline_output_links_source_code_from_hook_state(self):
        hook_state = create_hook_state()
        scene_path = normalize_path_string("scene.py")
        hook_state.captured_source_code[scene_path] = (
            "from manim import *\n\nclass GeneratedScene(Scene):\n    pass\n"
        )
        dispatcher = _MessageDispatcher(verbose=False, hook_state=hook_state)

        dispatcher.dispatch(
            _make_result_message(
                num_turns=1,
                structured_output={
                    "video_output": "/tmp/out.mp4",
                    "scene_file": "scene.py",
                    "scene_class": "GeneratedScene",
                },
            )
        )

        pipeline_output = dispatcher.get_pipeline_output()
        assert pipeline_output is not None
        assert pipeline_output.source_code == hook_state.captured_source_code[scene_path]

    def test_structured_output_uses_only_matching_scene_file(self):
        hook_state = create_hook_state()
        hook_state.captured_source_code[normalize_path_string("actual_scene.py")] = "print('hello')"
        dispatcher = _MessageDispatcher(verbose=False, hook_state=hook_state)

        dispatcher.dispatch(
            _make_result_message(
                num_turns=1,
                structured_output={
                    "video_output": "/tmp/out.mp4",
                    "scene_file": "different_scene.py",
                },
            )
        )

        pipeline_output = dispatcher.get_pipeline_output()
        assert pipeline_output is not None
        assert pipeline_output.source_code is None

    def test_dispatchers_keep_hook_snapshots_isolated(self):
        state_a = create_hook_state()
        state_b = create_hook_state()
        state_a.captured_source_code[normalize_path_string("scene_a.py")] = "print('A')"
        state_b.captured_source_code[normalize_path_string("scene_b.py")] = "print('B')"

        dispatcher_a = _MessageDispatcher(verbose=False, hook_state=state_a)
        dispatcher_b = _MessageDispatcher(verbose=False, hook_state=state_b)

        dispatcher_a.dispatch(
            _make_result_message(
                num_turns=1,
                structured_output={"video_output": "/a.mp4", "scene_file": "scene_a.py"},
            )
        )
        dispatcher_b.dispatch(
            _make_result_message(
                num_turns=1,
                structured_output={"video_output": "/b.mp4", "scene_file": "scene_b.py"},
            )
        )

        pipeline_output_a = dispatcher_a.get_pipeline_output()
        pipeline_output_b = dispatcher_b.get_pipeline_output()
        assert pipeline_output_a is not None
        assert pipeline_output_b is not None
        assert pipeline_output_a.source_code == "print('A')"
        assert pipeline_output_b.source_code == "print('B')"
