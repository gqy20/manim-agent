from ._test_main_dispatcher_helpers import _MessageDispatcher, _make_result_message


def test_persistable_output_includes_phase1_planning():
    d = _MessageDispatcher(verbose=False)
    d.dispatch(
        _make_result_message(
            num_turns=1,
            structured_output={
                "build_spec": {
                    "mode": "teaching-animation",
                    "learning_goal": "Explain a key idea.",
                    "audience": "Beginners",
                    "target_duration_seconds": 60,
                    "beats": [
                        {
                            "id": "beat_001_intro",
                            "title": "Intro",
                            "visual_goal": "Show title card.",
                            "narration_intent": "Set up context.",
                            "target_duration_seconds": 12,
                            "required_elements": ["title"],
                            "segment_required": True,
                        },
                    ],
                },
            },
        )
    )
    payload = d.get_persistable_pipeline_output()

    assert payload is not None
    assert payload["phase1_planning"] is not None
    assert payload["phase1_planning"]["build_spec"]["mode"] == "teaching-animation"
