from ._test_main_dispatcher_helpers import *

class TestTTSNarrationFlow:
    """楠岃瘉 run_pipeline 鍦ㄦ湁 narration 鏃朵紶缁?TTS锛屽惁鍒?fallback 鍒?user_text銆?""

    @pytest.mark.asyncio
    async def test_tts_uses_narration_when_available(self):
        """dispatcher 鏈?narration 鏃?TTS 鏀跺埌瑙ｈ璇嶈€岄潪 user_text銆?""
        mock_messages = [
            _make_assistant_message(_make_text_block("娓叉煋瀹屾垚")),
            _make_result_message(
                num_turns=1,
                **{"structured_output": {
                    "video_output": "/out.mp4",
                    "narration": "涓撲笟瑙ｈ璇嶅唴瀹?,
                }},
            ),
        ]
        captured_tts_text: list[str] = []

        async def capture_tts(text, **_kw):
            captured_tts_text.append(text)
            return MagicMock(audio_path="a.mp3", subtitle_path="sub.srt", duration_ms=1000)

        with (
            patch("manim_agent.__main__.query") as mock_query,
            patch("manim_agent.__main__.tts_client.synthesize", side_effect=capture_tts),
            patch("manim_agent.__main__.video_builder.build_final_video", new_callable=AsyncMock) as mock_vid,
        ):
            async def gen(*_a, **_k):
                for m in mock_messages:
                    yield m
            mock_query.side_effect = gen
            mock_vid.return_value = "final.mp4"

            await main_module.run_pipeline(
                user_text="鐢ㄦ埛鍘熷闇€姹傛弿杩?,
                output_path="/out.mp4",
                no_tts=False,
            )

        assert len(captured_tts_text) == 1
        assert captured_tts_text[0] == "涓撲笟瑙ｈ璇嶅唴瀹?

    @pytest.mark.asyncio
    async def test_tts_fallback_to_user_text(self):
        """鏃?narration 鏃?TTS 鏀跺埌鍘熷 user_text銆?""
        mock_messages = [
            _make_assistant_message(_make_text_block("娓叉煋瀹屾垚")),
            _make_result_message(
                num_turns=1,
                **{"structured_output": {"video_output": "/out.mp4"}},
            ),
        ]
        captured_tts_text: list[str] = []

        async def capture_tts(text, **_kw):
            captured_tts_text.append(text)
            return MagicMock(audio_path="a.mp3", subtitle_path="sub.srt", duration_ms=1000)

        with (
            patch("manim_agent.__main__.query") as mock_query,
            patch("manim_agent.__main__.tts_client.synthesize", side_effect=capture_tts),
            patch("manim_agent.__main__.video_builder.build_final_video", new_callable=AsyncMock) as mock_vid,
        ):
            async def gen(*_a, **_k):
                for m in mock_messages:
                    yield m
            mock_query.side_effect = gen
            mock_vid.return_value = "final.mp4"

            await main_module.run_pipeline(
                user_text="鐢ㄦ埛闇€姹?,
                output_path="/out.mp4",
                no_tts=False,
            )

        assert captured_tts_text == ["鐢ㄦ埛闇€姹?]


# 鈹€鈹€ Phase 5: structured_output 闆嗘垚 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€


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

    def test_task_notification_takes_priority_over_structured_output(self):
        """task_notification.output_file 鎼存柧缍旀稉鐑樻付瀵櫣娈戠憴鍡涱暥鏉堟挸鍤穱鈥冲娇閵?"""
        d = _MessageDispatcher(verbose=False)
        d.dispatch(TaskNotificationMessage(
            subtype="task_notification",
            data={},
            task_id="task-1",
            status="completed",
            output_file="/notification/out.mp4",
            summary="done",
            uuid="u1",
            session_id="s1",
        ))
        d.dispatch(_make_result_message(
            num_turns=1,
            **{"structured_output": {"video_output": "/struct.mp4", "scene_file": "s.py"}},
        ))

        po = d.get_pipeline_output()
        assert po is not None
        assert po.video_output == "/notification/out.mp4"

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



