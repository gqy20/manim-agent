"""Tests for the backend API layer."""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.models import TaskCreateRequest, TaskStatus
from backend.routes import set_store
from backend.task_store import TaskStore


@pytest.fixture(autouse=True)
def clean_persistence(tmp_path, monkeypatch):
    """Redirect persistence to temp dir so tests don't leak data."""
    monkeypatch.setattr(
        "backend.task_store._PERSISTENCE_FILE",
        tmp_path / "tasks.json",
    )


@pytest.fixture
def store():
    s = TaskStore()
    set_store(s)
    return s


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

    def test_create_task_surfaces_non_empty_failure_message(self, client, sample_request):
        async def failing_pipeline(**_kwargs):
            raise RuntimeError("Failed to start Claude Code: ") from OSError(
                "The system cannot find the file specified"
            )

        with patch("manim_agent.__main__.run_pipeline", failing_pipeline):
            resp = client.post("/api/tasks", json=sample_request.model_dump())

        assert resp.status_code == 201
        task_id = resp.json()["id"]

        for _ in range(20):
            task_resp = client.get(f"/api/tasks/{task_id}")
            assert task_resp.status_code == 200
            task = task_resp.json()
            if task["status"] == "failed":
                break
        else:
            pytest.fail("task did not transition to failed state")

        assert "The system cannot find the file specified" in task["error"]


class TestTaskStore:
    @pytest.mark.asyncio
    async def test_create_and_retrieve(self):
        store = TaskStore()
        req = TaskCreateRequest(user_text="test task")
        task = await store.create(req)
        assert task["id"]
        assert task["status"] == "pending"

        retrieved = await store.get(task["id"])
        assert retrieved is not None
        assert retrieved["user_text"] == "test task"

    @pytest.mark.asyncio
    async def test_update_status(self):
        store = TaskStore()
        req = TaskCreateRequest(user_text="test")
        task = await store.create(req)

        await store.update_status(task["id"], TaskStatus.RUNNING)
        updated = await store.get(task["id"])
        assert updated["status"] == "running"

        await store.update_status(
            task["id"], TaskStatus.COMPLETED, video_path="/tmp/out.mp4"
        )
        completed = await store.get(task["id"])
        assert completed["status"] == "completed"
        assert completed["video_path"] == "/tmp/out.mp4"
        assert completed["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_append_log(self):
        store = TaskStore()
        req = TaskCreateRequest(user_text="test")
        task = await store.create(req)

        await store.append_log(task["id"], "line 1")
        await store.append_log(task["id"], "line 2")

        logged = await store.get(task["id"])
        assert logged["logs"] == ["line 1", "line 2"]

    @pytest.mark.asyncio
    async def test_list_all_sorted(self):
        store = TaskStore()
        # Use unique text to avoid collision with persisted data
        import uuid
        prefix = uuid.uuid4().hex[:8]
        for i in range(3):
            await store.create(TaskCreateRequest(user_text=f"{prefix}_task_{i}"))

        tasks = await store.list_all(limit=3)
        assert len(tasks) == 3
        assert tasks[0]["created_at"] >= tasks[1]["created_at"]

    @pytest.mark.asyncio
    async def test_to_response(self):
        store = TaskStore()
        req = TaskCreateRequest(user_text="test")
        task = await store.create(req)
        response = store.to_response(task)
        assert response.id == task["id"]
        assert response.user_text == "test"


class TestSSEManager:
    def test_subscribe_push_done(self):
        from backend.sse_manager import SSESubscriptionManager

        mgr = SSESubscriptionManager()
        q = mgr.subscribe("t1")

        mgr.push("t1", "hello")
        mgr.push("t1", "world")
        mgr.done("t1")

        assert q.get_nowait() == "hello"
        assert q.get_nowait() == "world"
        assert q.get_nowait() is None

    def test_unsubscribe(self):
        from backend.sse_manager import SSESubscriptionManager

        mgr = SSESubscriptionManager()
        mgr.subscribe("t1")
        assert "t1" in mgr._queues
        mgr.unsubscribe("t1")
        assert "t1" not in mgr._queues

    def test_push_to_nonexistent_is_noop(self):
        from backend.sse_manager import SSESubscriptionManager

        mgr = SSESubscriptionManager()
        mgr.push("nonexistent", "should not crash")  # no error


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
