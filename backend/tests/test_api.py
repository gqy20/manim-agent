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
