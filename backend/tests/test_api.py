"""Tests for the backend API layer."""

from __future__ import annotations

import json
import os
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.models import TaskCreateRequest, TaskStatus
from backend.routes import set_store
from backend.task_store import TaskStore


@pytest.fixture(autouse=True)
def _env_setup(monkeypatch):
    """Set required env vars for tests."""
    monkeypatch.setenv(
        "DATABASE_URL",
        os.environ.get(
            "TEST_DATABASE_URL",
            "postgresql://neondb_owner:npg_nkDufTsx85NB@"
            "ep-tiny-cloud-ak4yq9kz.c-3.us-west-2.aws.neon.tech"
            "/neondb?sslmode=require",
        ),
    )
    # Enable inline (non-threaded) pipeline mode for TestClient compatibility.
    monkeypatch.setattr("backend.routes._USE_PIPELINE_THREAD", False)


@pytest.fixture
async def store():
    s = TaskStore()
    await s.start()
    set_store(s)
    yield s
    await s.close()


@pytest.fixture
def client(store):
    return TestClient(app)


@pytest.fixture
def sample_request():
    return TaskCreateRequest(
        user_text="解释勾股定理",
        voice_id="female-tianmei",
        quality="high",
    )


class TestHealthCheck:
    def test_health_returns_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


# ── 模块级异常工厂（raise ... from 是语句，无法放入 lambda） ──


def _make_oserror_chained():
    raise RuntimeError("Failed to start Claude Code: ") from OSError(
        "The system cannot find the file specified"
    )


def _make_cli_connection_error():
    from claude_agent_sdk import CLIConnectionError

    raise CLIConnectionError("Failed to start Claude Code") from NotImplementedError()


_ERROR_CASES = [
    pytest.param(
        _make_oserror_chained,
        ["The system cannot find the file specified"],
        id="oserror_chained",
    ),
    pytest.param(
        _make_cli_connection_error,
        ["CLIConnectionError", "NotImplementedError", "Failed to start Claude Code"],
        id="cli_connection_error",
    ),
    pytest.param(
        __import__("claude_agent_sdk", fromlist=["CLINotFoundError"])
        .CLINotFoundError("Claude Code not found"),
        lambda s: (  # 自定义断言：or 条件
            "CLINotFoundError" in s
            and ("not found" in s.lower() or "install" in s.lower())
        ),
        id="cli_not_found",
    ),
    pytest.param(
        __import__("claude_agent_sdk", fromlist=["ProcessError"])
        .ProcessError("Command failed", exit_code=1, stderr="permission denied"),
        ["ProcessError", "exit code", "1"],
        id="process_error",
    ),
    pytest.param(
        RuntimeError("something went wrong"),
        ["RuntimeError", "something went wrong"],
        id="generic_runtime_error",
    ),
]


class TestTaskCRUD:
    def test_create_task(self, client, sample_request):
        resp = client.post("/api/tasks", json=sample_request.model_dump())
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["user_text"] == "解释勾股定理"
        assert "id" in data
        assert len(data["id"]) == 8

    def test_list_tasks(self, client, sample_request):
        client.post("/api/tasks", json=sample_request.model_dump())

        resp = client.get("/api/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["tasks"]) >= 1

    def test_get_task(self, client, sample_request):
        create_resp = client.post("/api/tasks", json=sample_request.model_dump())
        task_id = create_resp.json()["id"]

        resp = client.get(f"/api/tasks/{task_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == task_id

    def test_get_task_not_found(self, client):
        resp = client.get("/api/tasks/nonexistent")
        assert resp.status_code == 404

    def test_video_not_ready(self, client, sample_request):
        create_resp = client.post("/api/tasks", json=sample_request.model_dump())
        task_id = create_resp.json()["id"]

        resp = client.get(f"/api/tasks/{task_id}/video")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_events_replay_completed_task(self, client, store):
        req = TaskCreateRequest(user_text="stream me")
        task = await store.create(req)
        await store.append_log(task["id"], "line 1")
        await store.append_log(task["id"], "line 2")
        await store.update_status(task["id"], TaskStatus.COMPLETED)

        with client.stream("GET", f"/api/tasks/{task['id']}/events") as resp:
            body = "".join(resp.iter_text())

        assert resp.status_code == 200
        assert '"event": "log"' in body
        assert "line 1" in body
        assert "line 2" in body
        assert '"event": "status"' in body
        assert "completed" in body

    # ── Error-surface 测试：parametrize 替代 5 个重复方法 ───

    @staticmethod
    def _wait_for_failed(client, task_id: str, timeout: int = 20) -> dict:
        """轮询任务直到 failed 状态，返回最终 task dict。"""
        for _ in range(timeout):
            task_resp = client.get(f"/api/tasks/{task_id}")
            assert task_resp.status_code == 200
            task = task_resp.json()
            if task["status"] == "failed":
                return task
        pytest.fail(f"task {task_id} did not transition to failed state")

    @pytest.mark.parametrize("exception_factory,expected_substrings", _ERROR_CASES)
    def test_create_task_error_surfaces_details(
        self,
        client,
        sample_request,
        exception_factory,
        expected_substrings,
    ):
        """各种异常类型均被正确捕获并暴露到 task.error 字段。"""
        exc = (
            exception_factory
            if isinstance(exception_factory, BaseException)
            else exception_factory()
        )

        async def failing_pipeline(**_kwargs):
            raise exc

        with patch("manim_agent.__main__.run_pipeline", failing_pipeline):
            resp = client.post("/api/tasks", json=sample_request.model_dump())
            assert resp.status_code == 201
            task = self._wait_for_failed(client, resp.json()["id"])

        if callable(expected_substrings) and not isinstance(expected_substrings, str):
            assert expected_substrings(task["error"])
        else:
            for sub in expected_substrings:
                assert sub in task["error"]


class TestTaskStore:
    """TaskStore CRUD 操作 — 共享 class-level 生命周期 fixture。"""

    @pytest.fixture(autouse=True)
    async def _store(self):
        """每个测试方法自动获取一个已启动的 TaskStore，测试结束后自动关闭。"""
        s = TaskStore()
        await s.start()
        yield s
        await s.close()

    @pytest.mark.asyncio
    async def test_create_and_retrieve(self, _store):
        req = TaskCreateRequest(user_text="test task")
        task = await _store.create(req)
        assert task["id"]
        assert task["status"] == "pending"

        retrieved = await _store.get(task["id"])
        assert retrieved is not None
        assert retrieved["user_text"] == "test task"

    @pytest.mark.asyncio
    async def test_update_status(self, _store):
        req = TaskCreateRequest(user_text="test")
        task = await _store.create(req)

        await _store.update_status(task["id"], TaskStatus.RUNNING)
        updated = await _store.get(task["id"])
        assert updated["status"] == "running"

        await _store.update_status(
            task["id"], TaskStatus.COMPLETED, video_path="/tmp/out.mp4",
        )
        completed = await _store.get(task["id"])
        assert completed["status"] == "completed"
        assert completed["video_path"] == "/tmp/out.mp4"
        assert completed["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_append_log(self, _store):
        req = TaskCreateRequest(user_text="test")
        task = await _store.create(req)

        await _store.append_log(task["id"], "line 1")
        await _store.append_log(task["id"], "line 2")

        logged = await _store.get(task["id"])
        assert logged["logs"] == ["line 1", "line 2"]

    @pytest.mark.asyncio
    async def test_list_all_sorted(self, _store):
        # Use unique text to avoid collision with persisted data
        import uuid

        prefix = uuid.uuid4().hex[:8]
        for i in range(3):
            await _store.create(TaskCreateRequest(user_text=f"{prefix}_task_{i}"))

        tasks = await _store.list_all(limit=3)
        assert len(tasks) == 3
        assert tasks[0]["created_at"] >= tasks[1]["created_at"]

    @pytest.mark.asyncio
    async def test_to_response(self, _store):
        req = TaskCreateRequest(user_text="test")
        task = await _store.create(req)
        response = _store.to_response(task)
        assert response.id == task["id"]
        assert response.user_text == "test"


class TestSSEManager:
    def test_subscribe_push_done(self):
        from backend.sse_manager import SSESubscriptionManager

        mgr = SSESubscriptionManager()
        q = mgr.subscribe("t1")
        import json

        mgr.push("t1", "hello")
        mgr.push("t1", "world")
        mgr.done("t1")

        # push() 现在返回序列化的 SSEEvent JSON
        assert json.loads(q.get_nowait())["data"] == "hello"
        assert json.loads(q.get_nowait())["data"] == "world"
        assert q.get_nowait() is None

    def test_unsubscribe(self):
        from backend.sse_manager import SSESubscriptionManager

        mgr = SSESubscriptionManager()
        q = mgr.subscribe("t1")
        assert "t1" in mgr._subscribers
        mgr.unsubscribe("t1", q)
        assert len(mgr._subscribers.get("t1", [])) == 0

    def test_push_to_nonexistent_is_noop(self):
        from backend.sse_manager import SSESubscriptionManager

        mgr = SSESubscriptionManager()
        mgr.push("nonexistent", "should not crash")  # no error

    def test_buffer_replay_on_subscribe(self):
        """v2: push() 无订阅者时缓冲，subscribe() 时自动回放。"""
        from backend.sse_manager import SSESubscriptionManager

        mgr = SSESubscriptionManager()
        import json

        # 推送时无订阅者 → 进入缓冲区
        mgr.push("t1", "buffered-1")
        mgr.push("t1", "buffered-2")

        # 订阅时回放缓冲事件
        q = mgr.subscribe("t1")
        assert json.loads(q.get_nowait())["data"] == "buffered-1"
        assert json.loads(q.get_nowait())["data"] == "buffered-2"

    def test_multiple_subscribers(self):
        """v2: 多个订阅者各自收到独立副本。"""
        from backend.sse_manager import SSESubscriptionManager

        mgr = SSESubscriptionManager()
        import json

        q1 = mgr.subscribe("t1")
        mgr.push("t1", "event-a")

        q2 = mgr.subscribe("t1")  # q2 应收到回放（含 event-a）
        mgr.push("t1", "event-b")

        # q1 收到 event-a + event-b
        assert json.loads(q1.get_nowait())["data"] == "event-a"
        assert json.loads(q1.get_nowait())["data"] == "event-b"

        # q2 收到回放(event-a) + event-b
        assert json.loads(q2.get_nowait())["data"] == "event-a"
        assert json.loads(q2.get_nowait())["data"] == "event-b"

    def test_cleanup(self):
        """cleanup() 清除所有状态。"""
        from backend.sse_manager import SSESubscriptionManager

        mgr = SSESubscriptionManager()
        mgr.subscribe("t1")
        mgr.push("t1", "x")
        assert mgr.get_buffer("t1")

        mgr.cleanup("t1")
        assert mgr.get_buffer("t1") == []
        assert "t1" not in mgr._subscribers


# ── Phase 6: PipelineOutput 数据传播 ──────────────────────────


class TestPipelineOutputDataModel:
    """验证后端 PipelineOutputData 模型。"""

    def test_model_exists(self):
        """PipelineOutputData 模型可导入。"""
        from backend.models import PipelineOutputData
        assert PipelineOutputData is not None

    def test_all_fields_default_none(self):
        """默认实例所有字段为 None。"""
        from backend.models import PipelineOutputData
        m = PipelineOutputData()
        assert m.video_output is None
        assert m.scene_file is None
        assert m.scene_class is None
        assert m.duration_seconds is None
        assert m.narration is None
        assert m.source_code is None

    def test_populated_model(self):
        """所有字段有值时正确存储。"""
        from backend.models import PipelineOutputData
        m = PipelineOutputData(
            video_output="/out.mp4",
            scene_file="s.py",
            scene_class="MyScene",
            duration_seconds=30,
            narration="解说词",
            source_code="code",
        )
        assert m.video_output == "/out.mp4"
        assert m.narration == "解说词"

    def test_task_response_has_pipeline_output_field(self):
        """TaskResponse 含 pipeline_output 字段。"""
        from backend.models import TaskResponse
        fields = TaskResponse.model_fields
        assert "pipeline_output" in fields


class TestTaskStorePipelineOutput:
    """验证 TaskStore 存取 pipeline_output 字段。"""

    @pytest.mark.asyncio
    async def test_create_task_pipeline_output_initially_none(self, store):
        """新创建的 task 的 pipeline_output 为 None。"""
        req = TaskCreateRequest(user_text="test")
        task = await store.create(req)
        assert "pipeline_output" in task
        assert task["pipeline_output"] is None

    @pytest.mark.asyncio
    async def test_update_status_stores_pipeline_output(self, store):
        """update_status 可写入 pipeline_output 数据。"""
        req = TaskCreateRequest(user_text="test")
        task = await store.create(req)

        await store.update_status(
            task["id"],
            TaskStatus.COMPLETED,
            video_path="/out.mp4",
            pipeline_output={
                "video_output": "/out.mp4",
                "scene_file": "s.py",
                "scene_class": "SClass",
                "narration": "专业解说",
            },
        )

        updated = await store.get(task["id"])
        po = updated["pipeline_output"]
        assert po is not None
        assert po["video_output"] == "/out.mp4"
        assert po["narration"] == "专业解说"

    @pytest.mark.asyncio
    async def test_to_response_includes_pipeline_output(self, store):
        """to_response() 序列化包含 pipeline_output。"""
        req = TaskCreateRequest(user_text="test")
        task = await store.create(req)
        response = store.to_response(task)
        assert response.pipeline_output is None

        # 设置后再序列化
        task["pipeline_output"] = {
            "video_output": "/x.mp4",
            "scene_file": "x.py",
        }
        response = store.to_response(task)
        assert response.pipeline_output is not None
        assert response.pipeline_output.video_output == "/x.mp4"


class TestAPIReturnsPipelineOutput:
    """验证 API 在任务完成时返回 pipeline_output 数据。"""

    @pytest.mark.asyncio
    async def test_completed_task_api_includes_pipeline_output(self, client, store):
        """完成任务的 GET 响应含 pipeline_output。"""
        req = TaskCreateRequest(user_text="测试输出")
        create_resp = client.post("/api/tasks", json=req.model_dump())
        task_id = create_resp.json()["id"]

        # 直接更新为完成状态并附带 pipeline_output
        await store.update_status(
            task_id,
            TaskStatus.COMPLETED,
            video_path="/final.mp4",
            pipeline_output={
                "video_output": "/final.mp4",
                "scene_file": "scene.py",
                "scene_class": "DemoScene",
                "duration_seconds": 20,
                "narration": "这是自动生成的解说词。",
            },
        )

        resp = client.get(f"/api/tasks/{task_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "pipeline_output" in data
        po = data["pipeline_output"]
        assert po["video_output"] == "/final.mp4"
        assert po["narration"] == "这是自动生成的解说词。"
