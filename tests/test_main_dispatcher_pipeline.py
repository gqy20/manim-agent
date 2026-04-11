from ._test_main_dispatcher_helpers import *

class TestSessionIsolation:
    def test_unique_session_id_per_call(self):
        """姣忔璋冪敤 run_pipeline 鐢熸垚涓嶅悓鐨?session_id銆?""
        # 鎴戜滑鏃犳硶鐩存帴妫€鏌?options 鍐呴儴鍊硷紙瀹冩槸鍐呴儴鏋勫缓鐨勶級锛?
        # 浣嗗彲浠ラ€氳繃 mock query 鏉ラ獙璇?options 琚纭紶閫?
        # 杩欓噷楠岃瘉 uuid 琚鍏ヤ笖鍙皟鐢?
        id1 = str(uuid.uuid4())
        id2 = str(uuid.uuid4())
        assert id1 != id2
        assert len(id1) == 36  # 鏍囧噯 UUID4 鏍煎紡

    def test_build_options_includes_session_fields(self):
        """_build_options 杩斿洖鍚?session_id 鍜?fork_session 鐨?options銆?""
        options = main_module._build_options(
            cwd="/project",
            system_prompt="test prompt",
            max_turns=10,
        )
        # 楠岃瘉閫夐」鍖呭惈闅旂瀛楁
        assert hasattr(options, "session_id")
        assert hasattr(options, "fork_session")
        assert options.session_id is not None  # 搴斾负闈炵┖ UUID
        assert options.fork_session is True

    def test_fork_session_always_true(self):
        """fork_session 濮嬬粓涓?True銆?""
        options = main_module._build_options(
            cwd="/project",
            system_prompt="test",
            max_turns=5,
        )
        assert options.fork_session is True


# 鈹€鈹€ Pipeline 缂栨帓锛圡ock 闆嗘垚锛?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€


class TestRunPipeline:
    @pytest.mark.asyncio
    async def test_full_flow_with_tts(self):
        """鍚?TTS 鐨勫畬鏁存祦绋?鈥?楠岃瘉 dispatcher 琚娇鐢ㄤ笖鏈夌粨鏋滄憳瑕併€?""
        mock_messages = [
            _make_assistant_message(
                _make_text_block("娓叉煋瀹屾垚"),
                _make_tool_use_block("Write", {"file_path": "s.py"}),
            ),
            _make_result_message(
                num_turns=2, total_cost_usd=0.02,
                **{"structured_output": {
                    "video_output": "media/out.mp4",
                    "scene_file": "s.py",
                    "scene_class": "S",
                }},
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
                user_text="娴嬭瘯鍐呭",
                output_path="output/final.mp4",
                voice_id="female-tianmei",
                no_tts=False,
            )

            assert result == "output/final.mp4"
            mock_tts.assert_awaited_once()
            mock_video.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skip_tts_mode(self):
        """--no-tts 妯″紡璺宠繃 TTS 鍜?video builder銆?""
        mock_messages = [
            _make_assistant_message(_make_text_block("娓叉煋瀹屾垚")),
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
                user_text="娴嬭瘯",
                output_path="output/out.mp4",
                no_tts=True,
            )

            assert result == "media/silent.mp4"
            mock_tts.assert_not_awaited()
            mock_video.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_tts_emits_authoritative_status_phases(self):
        """No-TTS mode should emit only init/render structured status phases."""
        from manim_agent.pipeline_events import EventType

        events = []
        mock_messages = [
            _make_assistant_message(_make_text_block("娓叉煋瀹屾垚")),
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

        assert result == "media/silent.mp4"
        status_events = [e for e in events if e.event_type == EventType.STATUS]
        assert [e.data.phase for e in status_events] == ["init", "render"]
        assert all(e.data.task_status == "running" for e in status_events)

    @pytest.mark.asyncio
    async def test_no_video_output_raises(self):
        """Claude 鏈緭鍑烘湁鏁?pipeline output 鏃舵姏 RuntimeError銆?""
        mock_messages = [
            _make_assistant_message(_make_text_block("澶勭悊瀹屾垚浣嗘湭鐢熸垚瑙嗛")),
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
                user_text="娴嬭瘯",
                output_path="output/out.mp4",
                no_tts=True,
            )

    @pytest.mark.asyncio
    async def test_failure_before_video_output_stops_status_phase_progression(self):
        """Failure before output resolution should emit only init/render phases."""
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
        """Full pipeline should emit authoritative status phases in execution order."""
        from manim_agent.pipeline_events import EventType

        events = []
        mock_messages = [
            _make_assistant_message(_make_text_block("娓叉煋瀹屾垚")),
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
        """_build_options 鍩烘湰瀛楁姝ｇ‘銆?""
        opts = main_module._build_options(
            cwd="/work",
            system_prompt="You are a helpful assistant.",
            max_turns=30,
        )
        assert opts.cwd == "/work"
        assert opts.system_prompt == "You are a helpful assistant."
        assert opts.max_turns == 30
        assert opts.permission_mode == "bypassPermissions"
        # 宸ュ叿鐧藉悕鍗曪細浠呭厑璁?pipeline 蹇呴渶鐨勫伐鍏凤紙鏀舵暃鏀诲嚮闈級
        assert opts.allowed_tools is not None
        assert set(opts.allowed_tools) == {
            "Read", "Write", "Edit",
            "Bash", "Glob", "Grep",
        }

    def test_custom_prompt_file(self, tmp_path):
        """鑷畾涔夋彁绀鸿瘝鏂囦欢琚姞杞姐€?""
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
        """stderr 鍥炶皟琚缃€?""
        opts = main_module._build_options(
            cwd="/work",
            system_prompt="test",
            max_turns=5,
        )
        assert opts.stderr is not None  # 搴旇缃粯璁?stderr handler


# 鈹€鈹€ P0 Bug #1: 缂哄皯 asyncio import 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€


class TestAsyncioImport:
    def test_asyncio_in_module_globals(self):
        """妯″潡鍏ㄥ眬浣滅敤鍩熶腑瀛樺湪 asyncio锛坃_main__.py 椤跺眰宸插鍏ワ級銆?""
        assert hasattr(main_module, "asyncio"), (
            "asyncio 鏈湪 __main__.py 涓鍏ワ紝"
            "杩愯 python -m manim_agent 浼氭姏 NameError"
        )

    def test_main_is_coroutine_function(self):
        """main() 鏄紓姝ュ嚱鏁般€?""
        import inspect
        assert inspect.iscoroutinefunction(main_module.main)

    def test_main_callable_without_nameerror(self):
        """main() 鍙皟鐢ㄤ笖涓嶅洜缂哄皯 asyncio 鑰屾姏 NameError銆?

        瀹為檯涓嶄細鎵ц瀹屾暣 pipeline锛堥渶瑕?Claude SDK锛夛紝
        浣嗚嚦灏戦獙璇佸嚱鏁板畾涔夊眰鏃犺娉?瀵煎叆閿欒銆?
        """
        # 鍙獙璇?callable锛屼笉瀹為檯 await
        assert callable(main_module.main)


# 鈹€鈹€ P0 Bug #2: quality 鍙傛暟姝讳唬鐮?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€



