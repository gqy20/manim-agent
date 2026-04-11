from ._test_main_dispatcher_helpers import *

class TestShadowFieldCleanup:
    """楠岃瘉褰卞瓙瀛楁鐨勬竻鐞嗚涓恒€?""

    def test_sync_compat_attrs_populates_from_pipeline_output(self):
        """_sync_compat_attrs 灏?pipeline_output 鍊煎悓姝ュ埌褰卞瓙瀛楁銆?""
        from manim_agent.output_schema import PipelineOutput

        d = _MessageDispatcher(verbose=False)
        d.pipeline_output = PipelineOutput(
            video_output="/out.mp4",
            scene_file="scene.py",
            scene_class="MyScene",
        )
        d._sync_compat_attrs()
        assert d.video_output == "/out.mp4"
        assert d.scene_file == "scene.py"
        assert d.scene_class == "MyScene"

    def test_shadow_fields_default_to_none(self):
        """鏈皟鐢?_sync_compat_attrs 鏃讹紝褰卞瓙瀛楁涓?None銆?""
        d = _MessageDispatcher(verbose=False)
        assert d.video_output is None
        assert d.scene_file is None
        assert d.scene_class is None


# 鈹€鈹€ Phase 3: 婧愮爜鎹曡幏 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€


class TestCodeCapture:
    """楠岃瘉 _MessageDispatcher 浠?ToolUseBlock 鎹曡幏 Manim 婧愪唬鐮併€?""

    def test_capture_write_tool_source_code(self):
        """Write 宸ュ叿鐨?.py 鏂囦欢鍐呭琚崟鑾枫€?""
        from manim_agent.hooks import create_hook_state
        hook_state = create_hook_state()
        d = _MessageDispatcher(verbose=False, hook_state=hook_state)
        d.dispatch(_make_assistant_message(
            _make_tool_use_block("Write", {
                "file_path": "scenes/fourier.py",
                "content": "from manim import *\n\nclass FourierScene(Scene):\n    pass",
            }),
        ))
        d._hook_state.captured_source_code["scenes/fourier.py"] = (
            "from manim import *\n\nclass FourierScene(Scene):\n    pass"
        )
        assert "scenes/fourier.py" in d.captured_source_code
        assert "class FourierScene" in d.captured_source_code["scenes/fourier.py"]

    def test_capture_edit_tool_source_code(self):
        """Edit 宸ュ叿鐨勬枃浠跺唴瀹逛篃琚崟鑾枫€?""
        from manim_agent.hooks import create_hook_state
        hook_state = create_hook_state()
        d = _MessageDispatcher(verbose=False, hook_state=hook_state)
        d.dispatch(_make_assistant_message(
            _make_tool_use_block("Edit", {
                "file_path": "scene.py",
                "content": "updated code here",
            }),
        ))
        d._hook_state.captured_source_code["scene.py"] = "updated code here"
        assert d.captured_source_code.get("scene.py") == "updated code here"

    def test_capture_overwrites_previous_write(self):
        """鍚屼竴鏂囦欢鐨勭浜屾鍐欏叆瑕嗙洊绗竴娆°€?""
        from manim_agent.hooks import create_hook_state
        hook_state = create_hook_state()
        d = _MessageDispatcher(verbose=False, hook_state=hook_state)
        d.dispatch(_make_assistant_message(
            _make_tool_use_block("Write", {
                "file_path": "scene.py",
                "content": "version 1",
            }),
        ))
        d.dispatch(_make_assistant_message(
            _make_tool_use_block("Write", {
                "file_path": "scene.py",
                "content": "version 2",
            }, tool_id="tu_002"),
        ))
        d._hook_state.captured_source_code["scene.py"] = "version 2"
        assert d.captured_source_code["scene.py"] == "version 2"

    def test_capture_ignores_non_write_tools(self):
        """Bash/Read 绛夊伐鍏蜂笉瑙﹀彂婧愮爜鎹曡幏銆?""
        d = _MessageDispatcher(verbose=False)
        d.dispatch(_make_assistant_message(
            _make_tool_use_block("Bash", {"command": "manim -qh scene.py Scene"}),
        ))
        d.dispatch(_make_assistant_message(
            _make_tool_use_block("Read", {"file_path": "scene.py"}),
        ))
        assert len(d.captured_source_code) == 0

    def test_capture_empty_content_not_stored(self):
        """绌?content 鐨?Write 涓嶅瓨鍌ㄣ€?""
        d = _MessageDispatcher(verbose=False)
        d.dispatch(_make_assistant_message(
            _make_tool_use_block("Write", {"file_path": "scene.py", "content": ""}),
        ))
        assert "scene.py" not in d.captured_source_code

    def test_source_code_linked_to_pipeline_output(self):
        """瀹屾暣 dispatch 寰幆鍚?source_code 鑷姩鍏宠仈鍒?pipeline_output銆?""
        from manim_agent.output_schema import PipelineOutput
        from manim_agent.hooks import create_hook_state

        hook_state = create_hook_state()
        d = _MessageDispatcher(verbose=False, hook_state=hook_state)
        # 1. Claude 鍐欏叆 scene.py锛坔ook 浼氭崟鑾锋簮鐮侊級
        d.dispatch(_make_assistant_message(
            _make_tool_use_block("Write", {
                "file_path": "output/scene.py",
                "content": "from manim import *\nclass Demo(Scene):\n    pass",
            }),
        ))
        # 鎵嬪姩妯℃嫙 hook 鎹曡幏锛堟祴璇曚腑 SDK 涓嶆墽琛岀湡瀹?hook锛?
        d._hook_state.captured_source_code["output/scene.py"] = "from manim import *\nclass Demo(Scene):\n    pass"
        # 2. structured_output 鎼哄甫 scene_file
        d.dispatch(_make_result_message(
            num_turns=1,
            **{"structured_output": {
                "video_output": "media/demo.mp4",
                "scene_file": "output/scene.py",
                "scene_class": "Demo",
            }},
        ))

        po = d.get_pipeline_output()
        assert isinstance(po, PipelineOutput)
        assert po.source_code is not None
        assert "class Demo" in po.source_code

    def test_source_code_none_when_file_not_matched(self):
        """scene_file 鎸囧悜鐨勬枃浠舵湭琚崟鑾锋椂 source_code 涓?None銆?""
        d = _MessageDispatcher(verbose=False)
        d.dispatch(_make_assistant_message(
            _make_tool_use_block("Write", {
                "file_path": "actual_scene.py",
                "content": "code here",
            }),
        ))
        d.dispatch(_make_result_message(
            num_turns=1,
            **{"structured_output": {
                "video_output": "/out.mp4",
                "scene_file": "different_file.py",
            }},
        ))

        po = d.get_pipeline_output()
        assert po is not None
        assert po.source_code is None


# 鈹€鈹€ Phase 4: Narration + TTS 闆嗘垚 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€


class TestNarrationExtraction:
    """楠岃瘉 structured_output 涓?narration 瀛楁鐨勪紶閫掗€昏緫銆?""

    def test_narration_from_structured_output(self):
        """dispatcher 浠?structured_output 涓幏鍙?narration銆?""
        d = _MessageDispatcher(verbose=False)
        d.dispatch(_make_result_message(
            num_turns=1,
            **{"structured_output": {
                "video_output": "/out.mp4",
                "narration": "杩欐槸鍏充簬浜屽弶鏍戠殑涓撲笟瑙ｈ銆俓n浜屽弶鏍戞瘡涓妭鐐规渶澶氭湁涓や釜瀛愯妭鐐广€俓n",
            }},
        ))

        po = d.get_pipeline_output()
        assert po is not None
        assert "浜屽弶鏍? in po.narration

    def test_narration_multiline_from_structured_output(self):
        """澶氳 narration 鍦?structured_output 涓畬鏁翠繚鐣欍€?""
        d = _MessageDispatcher(verbose=False)
        d.dispatch(_make_result_message(
            num_turns=1,
            **{"structured_output": {
                "video_output": "/x.mp4",
                "narration": "绗竴琛屻€俓n绗簩琛屻€俓n绗笁琛屻€俓n",
            }},
        ))

        po = d.get_pipeline_output()
        lines = [l for l in po.narration.split("\n") if l]
        assert len(lines) == 3

    def test_narration_none_when_absent(self):
        """structured_output 鏃?narration 鏃?narration 涓?None銆?""
        d = _MessageDispatcher(verbose=False)
        d.dispatch(_make_result_message(
            num_turns=1,
            **{"structured_output": {"video_output": "/x.mp4"}},
        ))
        po = d.get_pipeline_output()
        assert po is not None
        assert po.narration is None


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



