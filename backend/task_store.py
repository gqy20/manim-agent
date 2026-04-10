"""Task state management: in-memory store with JSON file persistence."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import TaskCreateRequest, TaskStatus, TaskResponse

_PERSISTENCE_FILE = Path("backend/data/tasks.json")


class TaskStore:
    """Thread-safe in-memory task store with file-based persistence."""

    def __init__(self) -> None:
        self._tasks: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._load()

    def _load(self) -> None:
        if _PERSISTENCE_FILE.exists():
            try:
                data = json.loads(_PERSISTENCE_FILE.read_text(encoding="utf-8"))
                self._tasks = data.get("tasks", {})
            except (json.JSONDecodeError, KeyError):
                self._tasks = {}

    async def save(self) -> None:
        async with self._lock:
            _PERSISTENCE_FILE.parent.mkdir(parents=True, exist_ok=True)
            _PERSISTENCE_FILE.write_text(
                json.dumps({"tasks": self._tasks}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    async def create(self, req: TaskCreateRequest) -> dict[str, Any]:
        task_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()
        task: dict[str, Any] = {
            "id": task_id,
            "user_text": req.user_text,
            "status": TaskStatus.PENDING.value,
            "created_at": now,
            "completed_at": None,
            "video_path": None,
            "error": None,
            "logs": [],
            "options": req.model_dump(),
        }
        self._tasks[task_id] = task
        await self.save()
        return task

    async def get(self, task_id: str) -> dict[str, Any] | None:
        return self._tasks.get(task_id)

    async def update_status(
        self, task_id: str, status: TaskStatus, **kwargs: Any
    ) -> None:
        task = self._tasks.get(task_id)
        if not task:
            return
        task["status"] = status.value
        for k, v in kwargs.items():
            task[k] = v
        if status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            task["completed_at"] = datetime.now(timezone.utc).isoformat()
        await self.save()

    async def append_log(self, task_id: str, line: str) -> None:
        task = self._tasks.get(task_id)
        if task:
            task["logs"].append(line)

    async def list_all(self, limit: int = 50) -> list[dict[str, Any]]:
        sorted_tasks = sorted(
            self._tasks.values(),
            key=lambda t: t["created_at"],
            reverse=True,
        )
        return sorted_tasks[:limit]

    @staticmethod
    def to_response(task: dict[str, Any]) -> TaskResponse:
        return TaskResponse(**{k: task[k] for k in TaskResponse.model_fields})
