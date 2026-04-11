from ._test_main_dispatcher_helpers import *

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
                num_turns=2,
                total_cost_usd=0.02,
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


class TestQualityIntegration:
    def test_quality_high_uses_qh_in_prompt(self):
        """quality='high' 鏃剁郴缁熸彁绀鸿瘝鍖呭惈 -qh 鏍囧織銆?""
        opts = main_module._build_options(
            cwd="/work",
            system_prompt=None,
            max_turns=10,
            quality="high",
        )
        assert "-qh" in opts.system_prompt

    def test_quality_medium_uses_qm_in_prompt(self):
        """quality='medium' 鏃剁郴缁熸彁绀鸿瘝鍖呭惈 -qm 鏍囧織锛堥潪 -qh锛夈€?""
        opts = main_module._build_options(
            cwd="/work",
            system_prompt=None,
            max_turns=10,
            quality="medium",
        )
        assert "-qm" in opts.system_prompt
        assert "-qh" not in opts.system_prompt

    def test_quality_low_uses_ql_in_prompt(self):
        """quality='low' 鏃剁郴缁熸彁绀鸿瘝鍖呭惈 -ql 鏍囧織銆?""
        opts = main_module._build_options(
            cwd="/work",
            system_prompt=None,
            max_turns=10,
            quality="low",
        )
        assert "-ql" in opts.system_prompt
        assert "-qh" not in opts.system_prompt

    def test_quality_default_is_high(self):
        """涓嶄紶 quality 鏃堕粯璁や娇鐢?high (-qh)銆?""
        opts = main_module._build_options(
            cwd="/work",
            system_prompt=None,
            max_turns=10,
        )
        assert "-qh" in opts.system_prompt

    def test_custom_system_prompt_not_overridden_by_quality(self):
        """鑷畾涔夌郴缁熸彁绀鸿瘝鏃?quality 涓嶈鐩栫敤鎴锋彁渚涚殑 prompt銆?""
        custom = "You are a custom assistant with no Manim flags."
        opts = main_module._build_options(
            cwd="/work",
            system_prompt=custom,
            max_turns=10,
            quality="low",
        )
        assert opts.system_prompt == custom

    @pytest.mark.asyncio
    async def test_run_pipeline_passes_quality_to_options(self):
        """run_pipeline 灏?quality 姝ｇ‘浼犻€掔粰 _build_options銆?

        閫氳繃 mock 楠岃瘉 _build_options 鏀跺埌浜嗘纭殑 quality 鍊笺€?
        """
        original_build = main_module._build_options

        call_capture: dict[str, Any] = {}

        def capture_build(*args, **kwargs):
            call_capture.update(kwargs)
            return original_build(*args, **kwargs)

        async def empty_query(**_kw):
            """杩斿洖绌哄紓姝ヨ凯浠ｅ櫒锛岃 pipeline 鍦?output 妫€鏌ュ澶辫触銆?""
            return
            yield  # type: ignore[misc]

        with patch("manim_agent.__main__._build_options", side_effect=capture_build):
            with (
                patch("manim_agent.__main__.query", side_effect=empty_query),
                pytest.raises(RuntimeError, match="valid pipeline output"),
            ):
                await main_module.run_pipeline(
                    user_text="test",
                    output_path="/tmp/out.mp4",
                    no_tts=True,
                    quality="medium",
                )

        assert call_capture.get("quality") == "medium"


# 鈹€鈹€ Phase 2: Dispatcher PipelineOutput 闆嗘垚 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€



