from ._test_main_dispatcher_helpers import *

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


class TestDispatcherPipelineOutput:
    """楠岃瘉 _MessageDispatcher 浣跨敤 PipelineOutput 鏇夸唬瑁稿瓧绗︿覆灞炴€с€?""

    def test_get_pipeline_output_returns_model(self):
        """dispatch 鍚?structured_output 鐨?ResultMessage 鍚庯紝get_pipeline_output() 杩斿洖 PipelineOutput 瀹炰緥銆?""
        from manim_agent.output_schema import PipelineOutput

        d = _MessageDispatcher(verbose=False)
        d.dispatch(_make_result_message(
            num_turns=1,
            **{"structured_output": {
                "video_output": "/media/out.mp4",
                "scene_file": "scene.py",
                "scene_class": "MyScene",
                "duration_seconds": 25,
            }},
        ))

        po = d.get_pipeline_output()
        assert isinstance(po, PipelineOutput)
        assert po.video_output == "/media/out.mp4"
        assert po.scene_file == "scene.py"
        assert po.scene_class == "MyScene"
        assert po.duration_seconds == 25.0

    def test_get_pipeline_output_none_when_no_structured_output(self):
        """鏃?structured_output 鏃?get_pipeline_output() 杩斿洖 None銆?""
        d = _MessageDispatcher(verbose=False)
        d.dispatch(_make_result_message(num_turns=1))
        assert d.get_pipeline_output() is None

    def test_get_video_output_from_task_notification_via_dispatch(self):
        """SDK task_notification 閫氳繃 dispatch 璁剧疆 pipeline_output 鍚庯紝get_video_output 杩斿洖姝ｇ‘鍊笺€?""
        d = _MessageDispatcher(verbose=False)
        d.dispatch(TaskNotificationMessage(
            subtype="task_notification",
            task_id="t1",
            status="completed",
            output_file="/sdk/out.mp4",
            summary="done",
            uuid="u1",
            session_id="s1",
            data={},
        ))
        assert d.get_video_output() == "/sdk/out.mp4"

    def test_get_pipeline_output_falls_back_to_rendered_mp4(self, tmp_path: Path):
        """鏈?completed task_notification 浣嗘棤 output_file 鏃讹紝鍙粠鏂囦欢绯荤粺鍙戠幇宸叉覆鏌撶殑 mp4銆?""
        video_path = tmp_path / "media" / "videos" / "scene" / "1080p60" / "demo.mp4"
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(b"fake-mp4")

        d = _MessageDispatcher(verbose=False, output_cwd=str(tmp_path))
        # 鍙戦€?completed 閫氱煡浠ュ惎鐢ㄦ枃浠剁郴缁熸壂鎻?
        d.dispatch(TaskNotificationMessage(
            subtype="task_notification",
            data={},
            task_id="t1",
            status="completed",
            output_file=None,
            summary="done",
            uuid="u1",
            session_id="s1",
        ))
        po = d.get_pipeline_output()

        assert po is not None
        assert po.video_output == str(video_path.resolve())


# 鈹€鈹€ TDD: get_video_output 鍗曡矾寰勫寲 + shadow field 娓呯悊 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€


class TestGetVideoOutputSinglePath:
    """楠岃瘉 get_video_output() 鏄?get_pipeline_output() 鐨勭函渚挎嵎鍖呰銆?""

    def test_delegates_to_pipeline_output(self):
        """pipeline_output 宸茶缃椂锛岀洿鎺ヨ繑鍥炲叾 video_output銆?""
        from manim_agent.output_schema import PipelineOutput

        d = _MessageDispatcher(verbose=False)
        d.pipeline_output = PipelineOutput(video_output="/out.mp4")
        assert d.get_video_output() == "/out.mp4"

    def test_returns_none_when_no_pipeline_output(self):
        """pipeline_output 涓?None 鏃惰繑鍥?None锛屼笉鍥為€€鍒板奖瀛愬瓧娈点€?""
        d = _MessageDispatcher(verbose=False)
        assert d.get_video_output() is None

    def test_returns_none_even_if_shadow_field_set(self):
        """鍗充娇鐩存帴璁剧疆 video_output 褰卞瓙瀛楁锛実et_video_output 涔熶笉搴斾緷璧栧畠銆?""
        from manim_agent.output_schema import PipelineOutput

        d = _MessageDispatcher(verbose=False)
        d.video_output = "/shadow.mp4"
        assert d.get_video_output() is None

    def test_task_notification_sets_pipeline_output_correctly(self):
        """task_notification 閫氳繃 dispatch 姝ｇ‘璁剧疆 pipeline_output銆?""
        d = _MessageDispatcher(verbose=False)
        d.dispatch(TaskNotificationMessage(
            subtype="task_notification",
            task_id="t1",
            status="completed",
            output_file="/task/out.mp4",
            summary="render done",
            uuid="u1",
            session_id="s1",
            data={},
        ))
        po = d.get_pipeline_output()
        assert po is not None
        assert po.video_output == "/task/out.mp4"
        assert d.get_video_output() == "/task/out.mp4"

    def test_structured_output_does_not_overwrite_existing_pipeline_output(self):
        """褰?pipeline_output 宸茶 task_notification 璁剧疆鍚庯紝structured_output 涓嶅簲瑕嗙洊瀹冦€?""
        from manim_agent.output_schema import PipelineOutput

        d = _MessageDispatcher(verbose=False)
        d.dispatch(TaskNotificationMessage(
            subtype="task_notification",
            task_id="t1",
            status="completed",
            output_file="/task/out.mp4",
            summary="render done",
            uuid="u1",
            session_id="s1",
            data={},
        ))
        assert d.get_video_output() == "/task/out.mp4"
        d.dispatch(_make_result_message(
            num_turns=1,
            **{"structured_output": {"video_output": "/structured/out.mp4"}},
        ))
        assert d.get_video_output() == "/task/out.mp4"



