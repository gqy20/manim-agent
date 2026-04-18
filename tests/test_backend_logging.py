from __future__ import annotations

import logging
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi import HTTPException

from backend.content_clarifier import ContentClarifyError, clarify_content
from backend.log_config import (
    bind_log_context,
    clear_log_context,
    configure_logging,
    get_log_context,
    install_request_logging_middleware,
    log_event,
)
from backend.models import ContentClarifyData, ContentClarifyRequest, TaskStatus
from backend.routes import (
    clarify_content_route,
    create_task,
    get_task,
    get_video,
    list_tasks,
    receive_frontend_logs,
    set_store,
)


class _FakeAsyncClient:
    def __init__(self, response: httpx.Response) -> None:
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, *args, **kwargs) -> httpx.Response:
        return self._response


class TestLogContext:
    def test_log_event_merges_bound_context(self, caplog):
        logger = logging.getLogger("backend.test")

        clear_log_context()
        bind_log_context(request_id="req-123", task_id="task-456")
        with caplog.at_level(logging.INFO):
            log_event(logger, logging.INFO, "test_event", route="/api/test")
        clear_log_context()

        record = caplog.records[-1]
        assert record.msg == "test_event"
        assert record.request_id == "req-123"
        assert record.task_id == "task-456"
        assert record.route == "/api/test"

    @pytest.mark.asyncio
    async def test_request_logging_middleware_binds_request_id(self, caplog):
        app = FastAPI()
        install_request_logging_middleware(app)

        @app.get("/ping")
        async def _ping():
            return {"ok": True}

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            with caplog.at_level(logging.INFO):
                response = await client.get("/ping", headers={"x-request-id": "req-abc"})

        assert response.status_code == 200
        assert response.headers["x-request-id"] == "req-abc"
        started = next(record for record in caplog.records if record.msg == "request_started")
        finished = next(record for record in caplog.records if record.msg == "request_finished")
        assert started.request_id == "req-abc"
        assert finished.request_id == "req-abc"
        assert finished.status_code == 200

    def test_configure_logging_installs_root_handlers(self, tmp_path):
        configure_logging(log_dir=tmp_path)
        root = logging.getLogger()
        assert len(root.handlers) == 2


class TestContentClarifierLogging:
    @pytest.mark.asyncio
    async def test_clarify_content_logs_success(self, monkeypatch, caplog):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        response = httpx.Response(
            200,
            json={
                "content": [
                    {
                        "type": "text",
                        "text": (
                            '{"topic_interpretation":"圆周率","core_question":"什么是圆周率",'
                            '"prerequisite_concepts":[],"explanation_path":["定义"],'
                            '"scope_boundaries":[],"optional_branches":[],"animation_focus":["圆"],'
                            '"ambiguity_notes":[],"clarified_brief_cn":"讲清圆周率",'
                            '"recommended_request_cn":"请讲清圆周率"}'
                        ),
                    }
                ]
            },
        )

        with (
            patch("backend.content_clarifier.httpx.AsyncClient", return_value=_FakeAsyncClient(response)),
            caplog.at_level(logging.INFO),
        ):
            result = await clarify_content("圆周率")

        assert isinstance(result, ContentClarifyData)
        events = [record.msg for record in caplog.records]
        assert "clarifier_request_started" in events
        assert "clarifier_response_received" in events
        assert "clarifier_completed" in events
        started = next(record for record in caplog.records if record.msg == "clarifier_request_started")
        assert started.text_len == 3

    @pytest.mark.asyncio
    async def test_clarify_content_logs_http_error(self, monkeypatch, caplog):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        response = httpx.Response(503, text="upstream down")

        with (
            patch("backend.content_clarifier.httpx.AsyncClient", return_value=_FakeAsyncClient(response)),
            caplog.at_level(logging.INFO),
            pytest.raises(ContentClarifyError, match="Clarifier API error 503"),
        ):
            await clarify_content("圆周率")

        error_record = next(record for record in caplog.records if record.msg == "clarifier_http_error")
        assert error_record.status_code == 503


class TestRouteLogging:
    @pytest.mark.asyncio
    async def test_create_task_logs_request_and_creation(self, caplog):
        clear_log_context()
        bind_log_context(request_id="req-123")
        req = SimpleNamespace(
            user_text="讲解圆周率",
            voice_id="female-tianmei",
            model="speech-2.8-hd",
            quality="high",
            preset="default",
            no_tts=False,
            bgm_enabled=False,
            bgm_volume=0.12,
            target_duration_seconds=60,
            bgm_prompt=None,
        )
        task_payload = {
            "id": "task-123",
            "user_text": req.user_text,
            "status": TaskStatus.PENDING,
            "created_at": "2026-01-01T00:00:00+00:00",
            "completed_at": None,
            "video_path": None,
            "error": None,
            "options": {},
            "pipeline_output": None,
        }
        store = SimpleNamespace(
            create=AsyncMock(return_value=task_payload),
            append_log=AsyncMock(),
            to_response=lambda item: item,
        )
        set_store(store)

        created_coroutines: list[object] = []

        def _capture_task(coro):
            created_coroutines.append(coro)
            coro.close()
            return SimpleNamespace()

        with (
            patch("backend.routes._USE_PIPELINE_THREAD", False),
            patch("backend.routes.asyncio.create_task", side_effect=_capture_task),
            caplog.at_level(logging.INFO),
        ):
            response = await create_task(req)

        assert response["id"] == "task-123"
        requested = next(record for record in caplog.records if record.msg == "task_create_requested")
        assert requested.text_len == len(req.user_text)
        assert requested.request_id == "req-123"
        created = next(record for record in caplog.records if record.msg == "task_created")
        assert created.task_id == "task-123"
        assert created.request_id == "req-123"
        assert created_coroutines
        clear_log_context()

    @pytest.mark.asyncio
    async def test_create_task_propagates_request_context_into_thread_pipeline(self, caplog):
        clear_log_context()
        bind_log_context(request_id="req-thread")
        req = SimpleNamespace(
            user_text="讲解圆周率",
            voice_id="female-tianmei",
            model="speech-2.8-hd",
            quality="high",
            preset="default",
            no_tts=False,
            bgm_enabled=False,
            bgm_volume=0.12,
            target_duration_seconds=60,
            bgm_prompt=None,
        )
        task_payload = {
            "id": "task-thread",
            "user_text": req.user_text,
            "status": TaskStatus.PENDING,
            "created_at": "2026-01-01T00:00:00+00:00",
            "completed_at": None,
            "video_path": None,
            "error": None,
            "options": {},
            "pipeline_output": None,
        }
        store = SimpleNamespace(
            create=AsyncMock(return_value=task_payload),
            append_log=AsyncMock(),
            update_status=AsyncMock(),
            to_response=lambda item: item,
        )
        set_store(store)

        captured_context: dict[str, object] = {}
        real_thread = threading.Thread

        async def _fake_pipeline_body(**kwargs):
            captured_context.update(get_log_context())
            return ("video.mp4", None)

        class _ImmediateThread:
            def __init__(self, *, target, daemon):
                self._target = target

            def start(self):
                thread = real_thread(target=self._target, daemon=True)
                thread.start()
                thread.join()

        with (
            patch("backend.routes._pipeline_body", side_effect=_fake_pipeline_body),
            patch("backend.routes.threading.Thread", side_effect=lambda **kwargs: _ImmediateThread(**kwargs)),
            caplog.at_level(logging.INFO),
        ):
            response = await create_task(req)

        assert response["id"] == "task-thread"
        started = next(record for record in caplog.records if record.msg == "pipeline_thread_started")
        assert started.request_id == "req-thread"
        assert started.task_id == "task-thread"
        assert captured_context["request_id"] == "req-thread"
        assert captured_context["task_id"] == "task-thread"
        clear_log_context()

    @pytest.mark.asyncio
    async def test_create_task_logs_thread_task_completion(self, caplog):
        clear_log_context()
        bind_log_context(request_id="req-complete")
        req = SimpleNamespace(
            user_text="讲解圆周率",
            voice_id="female-tianmei",
            model="speech-2.8-hd",
            quality="high",
            preset="default",
            no_tts=False,
            bgm_enabled=False,
            bgm_volume=0.12,
            target_duration_seconds=60,
            bgm_prompt=None,
        )
        task_payload = {
            "id": "task-complete",
            "user_text": req.user_text,
            "status": TaskStatus.PENDING,
            "created_at": "2026-01-01T00:00:00+00:00",
            "completed_at": None,
            "video_path": None,
            "error": None,
            "options": {},
            "pipeline_output": None,
        }
        store = SimpleNamespace(
            create=AsyncMock(return_value=task_payload),
            append_log=AsyncMock(),
            update_status=AsyncMock(),
            to_response=lambda item: item,
        )
        set_store(store)
        real_thread = threading.Thread

        async def _fake_pipeline_body(**kwargs):
            return ("video.mp4", None)

        class _ImmediateThread:
            def __init__(self, *, target, daemon):
                self._target = target

            def start(self):
                thread = real_thread(target=self._target, daemon=True)
                thread.start()
                thread.join()

        with (
            patch("backend.routes._pipeline_body", side_effect=_fake_pipeline_body),
            patch("backend.routes.threading.Thread", side_effect=lambda **kwargs: _ImmediateThread(**kwargs)),
            caplog.at_level(logging.INFO),
        ):
            await create_task(req)

        completed = next(record for record in caplog.records if record.msg == "task_completed")
        assert completed.request_id == "req-complete"
        assert completed.task_id == "task-complete"
        assert completed.task_status == TaskStatus.COMPLETED.value
        assert completed.video_path == "video.mp4"
        clear_log_context()

    @pytest.mark.asyncio
    async def test_create_task_logs_thread_task_failure(self, caplog):
        clear_log_context()
        bind_log_context(request_id="req-fail")
        req = SimpleNamespace(
            user_text="讲解圆周率",
            voice_id="female-tianmei",
            model="speech-2.8-hd",
            quality="high",
            preset="default",
            no_tts=False,
            bgm_enabled=False,
            bgm_volume=0.12,
            target_duration_seconds=60,
            bgm_prompt=None,
        )
        task_payload = {
            "id": "task-fail",
            "user_text": req.user_text,
            "status": TaskStatus.PENDING,
            "created_at": "2026-01-01T00:00:00+00:00",
            "completed_at": None,
            "video_path": None,
            "error": None,
            "options": {},
            "pipeline_output": None,
        }
        store = SimpleNamespace(
            create=AsyncMock(return_value=task_payload),
            append_log=AsyncMock(),
            update_status=AsyncMock(),
            to_response=lambda item: item,
        )
        set_store(store)
        real_thread = threading.Thread

        async def _fake_pipeline_body(**kwargs):
            raise RuntimeError("boom")

        class _ImmediateThread:
            def __init__(self, *, target, daemon):
                self._target = target

            def start(self):
                thread = real_thread(target=self._target, daemon=True)
                thread.start()
                thread.join()

        with (
            patch("backend.routes._pipeline_body", side_effect=_fake_pipeline_body),
            patch("backend.routes.threading.Thread", side_effect=lambda **kwargs: _ImmediateThread(**kwargs)),
            caplog.at_level(logging.INFO),
        ):
            await create_task(req)

        failed = next(record for record in caplog.records if record.msg == "task_failed")
        assert failed.request_id == "req-fail"
        assert failed.task_id == "task-fail"
        assert failed.task_status == TaskStatus.FAILED.value
        assert failed.error_type == "RuntimeError"
        clear_log_context()

    @pytest.mark.asyncio
    async def test_clarify_content_route_logs_success(self, caplog):
        req = ContentClarifyRequest(user_text="傅里叶变换")
        clarification = ContentClarifyData(
            topic_interpretation="傅里叶变换",
            core_question="为什么能切到频域",
            prerequisite_concepts=["周期函数"],
            explanation_path=["从周期到频谱"],
            scope_boundaries=[],
            optional_branches=[],
            animation_focus=["频谱"],
            ambiguity_notes=[],
            clarified_brief_cn="讲清傅里叶变换",
            recommended_request_cn="请讲清傅里叶变换",
        )

        with (
            patch("backend.routes.clarify_content", new=AsyncMock(return_value=clarification)),
            caplog.at_level(logging.INFO),
        ):
            response = await clarify_content_route(req)

        assert response.clarification.core_question == "为什么能切到频域"
        events = [record.msg for record in caplog.records]
        assert "clarify_content_requested" in events
        assert "clarify_content_succeeded" in events

    @pytest.mark.asyncio
    async def test_get_task_logs_missing_task(self, caplog):
        store = SimpleNamespace(get=AsyncMock(return_value=None))
        set_store(store)

        with caplog.at_level(logging.INFO), pytest.raises(HTTPException, match="Task not found"):
            await get_task("missing-task")

        record = next(record for record in caplog.records if record.msg == "task_not_found")
        assert record.task_id == "missing-task"

    @pytest.mark.asyncio
    async def test_get_video_logs_video_not_ready(self, caplog):
        store = SimpleNamespace(
            get=AsyncMock(
                return_value={
                    "id": "task-1",
                    "status": TaskStatus.RUNNING.value,
                    "video_path": None,
                }
            )
        )
        set_store(store)

        with caplog.at_level(logging.INFO), pytest.raises(HTTPException, match="Video not ready"):
            await get_video("task-1")

        record = next(record for record in caplog.records if record.msg == "task_video_not_ready")
        assert record.task_id == "task-1"

    @pytest.mark.asyncio
    async def test_list_tasks_logs_count(self, caplog):
        task_payload = {
            "id": "task-1",
            "user_text": "讲解圆周率",
            "status": TaskStatus.PENDING,
            "created_at": "2026-01-01T00:00:00+00:00",
            "completed_at": None,
            "video_path": None,
            "error": None,
            "options": {},
            "pipeline_output": None,
        }
        store = SimpleNamespace(
            list_all=AsyncMock(return_value=[task_payload]),
            to_response=lambda item: item,
        )
        set_store(store)

        with caplog.at_level(logging.INFO):
            response = await list_tasks(limit=10)

        assert response.total == 1
        record = next(record for record in caplog.records if record.msg == "task_list_requested")
        assert record.limit == 10
        completed = next(record for record in caplog.records if record.msg == "task_list_succeeded")
        assert completed.count == 1

    @pytest.mark.asyncio
    async def test_frontend_logs_route_logs_batch_stats(self, caplog):
        class _FakeRequest:
            async def json(self):
                return [
                    {"sessionId": "s1", "level": "info", "message": "a"},
                    {"sessionId": "s1", "level": "warn", "message": "b"},
                    {"sessionId": "s2", "level": "error", "message": "c"},
                ]

        with caplog.at_level(logging.INFO):
            response = await receive_frontend_logs(_FakeRequest())

        assert response.status_code == 204
        record = next(record for record in caplog.records if record.msg == "frontend_logs_received")
        assert record.entries_count == 3
        assert record.session_count == 2
