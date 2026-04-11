from ._test_main_dispatcher_helpers import *

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

    def test_get_pipeline_output_from_result_json_fallback(self):
        d = _MessageDispatcher(verbose=False)
        d.dispatch(_make_result_message(
            num_turns=1,
            result=json.dumps({
                "video_output": "/result/out.mp4",
                "scene_file": "scene.py",
                "narration": "hello",
            }),
        ))

        po = d.get_pipeline_output()

        assert po is not None
        assert po.video_output == "/result/out.mp4"
        assert po.scene_file.endswith("scene.py")
        assert po.narration == "hello"

    def test_get_pipeline_output_from_result_text_path_fallback(self):
        video_path = Path("D:/tmp/rendered.mp4").resolve()
        with patch("manim_agent.dispatcher.Path.exists", return_value=True):
            d = _MessageDispatcher(verbose=False)
            d.dispatch(_make_result_message(
                num_turns=1,
                result=f"Rendered successfully: {video_path}",
            ))

            po = d.get_pipeline_output()

        assert po is not None
        assert po.video_output == str(video_path)

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
        """Fallback to filesystem artifacts only after an SDK completed signal."""
        video_path = tmp_path / "media" / "videos" / "scene" / "1080p60" / "demo.mp4"
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(b"fake-mp4")

        d = _MessageDispatcher(verbose=False, output_cwd=str(tmp_path))
        d.dispatch(TaskNotificationMessage(
            subtype="task_notification",
            task_id="t1",
            status="completed",
            output_file=None,
            summary="done",
            uuid="u1",
            session_id="s1",
            data={},
        ))
        po = d.get_pipeline_output()

        assert po is not None
        assert po.video_output == str(video_path.resolve())

    def test_get_pipeline_output_does_not_scan_filesystem_without_completed_signal(self, tmp_path: Path):
        """Filesystem fallback should not run before the SDK reports completion."""
        video_path = tmp_path / "media" / "videos" / "scene" / "1080p60" / "demo.mp4"
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(b"fake-mp4")

        d = _MessageDispatcher(verbose=False, output_cwd=str(tmp_path))

        assert d.get_pipeline_output() is None


# 鈹€鈹€ TDD: get_video_output 鍗曡矾寰勫寲 + shadow field 娓呯悊 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€


    def test_get_pipeline_output_scans_filesystem_after_result_message(self, tmp_path: Path):
        video_path = tmp_path / "media" / "videos" / "scene" / "1080p60" / "demo.mp4"
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(b"fake-mp4")

        d = _MessageDispatcher(verbose=False, output_cwd=str(tmp_path))
        d.dispatch(_make_result_message(num_turns=1, result="render finished"))

        po = d.get_pipeline_output()

        assert po is not None
        assert po.video_output == str(video_path.resolve())


class TestGetVideoOutputSinglePath:
    """楠岃瘉 get_video_output() 鏄?get_pipeline_output() 鐨勭函渚挎嵎鍖呰銆?

    閲嶆瀯鐩爣锛氱Щ闄?self.video_output 褰卞瓙瀛楁鐨勪笁璺?fallback锛?
    浣?get_video_output() 浠呭鎵樼粰 get_pipeline_output().video_output銆?
    """

    def test_delegates_to_pipeline_output(self):
        """pipeline_output 宸茶缃椂锛岀洿鎺ヨ繑鍥炲叾 video_output銆?""
        from manim_agent.output_schema import PipelineOutput

        d = _MessageDispatcher(verbose=False)
        d.pipeline_output = PipelineOutput(video_output="/out.mp4")
        assert d.get_video_output() == "/out.mp4"

    def test_returns_none_when_no_pipeline_output(self):
        """pipeline_output 涓?None 鏃惰繑鍥?None锛屼笉鍥為€€鍒板奖瀛愬瓧娈点€?""
        d = _MessageDispatcher(verbose=False)
        # 涓嶈缃?pipeline_output锛屼篃涓嶈缃?video_output 褰卞瓙瀛楁
        assert d.get_video_output() is None

    def test_returns_none_even_if_shadow_field_set(self):
        """鍗充娇鐩存帴璁剧疆 video_output 褰卞瓙瀛楁锛実et_video_output 涔熶笉搴斾緷璧栧畠銆?

        杩欐槸閲嶆瀯鍚庣殑琛屼负锛氬奖瀛愬瓧娈典笉鍐嶆槸鐙珛鏁版嵁婧愩€?
        """
        from manim_agent.output_schema import PipelineOutput

        d = _MessageDispatcher(verbose=False)
        # 鐩存帴璁剧疆褰卞瓙瀛楁锛堟棫妯″紡鍏佽鐨勶級
        d.video_output = "/shadow.mp4"
        # 浣?pipeline_output 涓?None 鈫?搴旇繑鍥?None锛堥噸鏋勫悗琛屼负锛?
        # 娉ㄦ剰锛氭娴嬭瘯鍦ㄩ噸鏋勫墠浼?FAIL锛堟棫浠ｇ爜杩斿洖 /shadow.mp4锛?
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
        # get_video_output 搴旈€氳繃 pipeline_output 鑾峰彇鍚屼竴鍊?
        assert d.get_video_output() == "/task/out.mp4"

    def test_structured_output_does_not_overwrite_existing_pipeline_output(self):
        """褰?pipeline_output 宸茶 task_notification 璁剧疆鍚庯紝
        structured_output 涓嶅簲瑕嗙洊瀹冦€?""
        from manim_agent.output_schema import PipelineOutput

        d = _MessageDispatcher(verbose=False)
        # 1. 鍏?dispatch task_notification锛堣缃?pipeline_output锛?
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
        first_video = d.get_video_output()
        assert first_video == "/task/out.mp4"
        # 2. 鍐?dispatch structured_output 鐨?ResultMessage
        d.dispatch(_make_result_message(
            num_turns=1,
            **{"structured_output": {"video_output": "/structured/out.mp4"}},
        ))
        # 3. pipeline_output 搴斾繚鎸?task_notification 鐨勫€?
        assert d.get_video_output() == "/task/out.mp4"


class TestShadowFieldCleanup:
    """楠岃瘉褰卞瓙瀛楁锛坴ideo_output/scene_file/scene_class锛夌殑娓呯悊銆?

    閲嶆瀯鐩爣锛氳繖浜涘瓧娈典笉鍐嶄綔涓虹嫭绔嬫暟鎹簮瀛樺湪锛?
    鎵€鏈夋暟鎹粺涓€閫氳繃 pipeline_output 璁块棶銆?
    """

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



