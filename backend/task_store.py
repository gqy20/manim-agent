"""Task state management: PostgreSQL-backed store (Neon).

Replaces the previous JSON-file implementation with asyncpg + PostgreSQL.
The public API is kept compatible so ``routes.py`` requires minimal changes.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import asyncpg

from .models import TaskCreateRequest, TaskStatus, TaskResponse


def _get_database_url() -> str:
    """Return the PostgreSQL connection URL from environment."""
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. "
            "Copy .env.example to .env and add your Neon URL."
        )
    return url


class TaskStore:
    """Async PostgreSQL task store with connection pooling."""

    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    # ── Lifecycle ───────────────────────────────────────────

    async def start(self) -> None:
        """Create the connection pool (call during app lifespan)."""
        self._pool = await asyncpg.create_pool(
            _get_database_url(),
            min_size=2,
            max_size=10,
        )

    async def save(self) -> None:
        """No-op for PostgreSQL — writes are already transactional."""
        pass

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError(
                "TaskStore not started. Call await store.start() first.",
            )
        return self._pool

    # ── CRUD ────────────────────────────────────────────────

    async def create(self, req: TaskCreateRequest) -> dict[str, Any]:
        task_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc)
        options_json = json.dumps(req.model_dump(), ensure_ascii=False)

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO tasks
                   (id, user_text, status, created_at, options)
                   VALUES ($1, $2, 'pending', $3, $4::jsonb)
                   RETURNING id, user_text, status,
                     created_at, completed_at, video_path,
                     error, options, pipeline_output,
                     updated_at""",
                task_id,
                req.user_text,
                now,
                options_json,
            )

        return _row_to_dict(row)

    async def get(self, task_id: str) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT t.*,
                          COALESCE(
                            ARRAY(
                              SELECT l.content FROM task_logs l
                              WHERE l.task_id = t.id
                              ORDER BY l.id ASC LIMIT 500
                            ),
                            '{}'::TEXT[]
                          ) AS logs
                   FROM tasks t WHERE t.id = $1""",
                task_id,
            )
        if row is None:
            return None
        return _row_to_dict(row)

    async def update_status(
        self, task_id: str, status: TaskStatus, **kwargs: Any
    ) -> None:
        completed_at = (
            datetime.now(timezone.utc)
            if status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
            else None
        )

        async with self.pool.acquire() as conn:
            sets = ["status = $2"]
            vals: list[Any] = [task_id, status.value]
            idx = 3

            if completed_at is not None:
                sets.append(f"completed_at = ${idx}")
                vals.append(completed_at)
                idx += 1

            for k, v in kwargs.items():
                if k == "pipeline_output" and v is not None:
                    v = json.dumps(v, ensure_ascii=False)
                    sets.append(f"{k} = ${idx}::jsonb")
                else:
                    sets.append(f"{k} = ${idx}")
                vals.append(v)
                idx += 1

            sets.append(f"updated_at = ${idx}")
            vals.append(datetime.now(timezone.utc))

            sql = f"UPDATE tasks SET {', '.join(sets)} WHERE id = $1"
            await conn.execute(sql, *vals)

    async def append_log(self, task_id: str, line: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO task_logs (task_id, content) VALUES ($1, $2)",
                task_id,
                line,
            )

    async def list_all(self, limit: int = 50) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT * FROM tasks
                   ORDER BY created_at DESC
                   LIMIT $1""",
                limit,
            )
        return [_row_to_dict(r) for r in rows]

    # ── Compatibility: expose _tasks for startup banner ──────

    @property
    def _tasks(self) -> dict[str, Any]:
        """Legacy compat property used by the startup banner.

        Returns an empty dict since we no longer hold tasks in memory.
        Override the banner to query DB instead if needed.
        """
        return {}


# ── Helpers ────────────────────────────────────────────────


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    """Convert an asyncpg Record to a plain dict, handling JSONB fields."""
    d = dict(row)
    # Ensure logs field exists (from the JOIN subquery or default)
    if "logs" not in d:
        d["logs"] = []
    if "pipeline_output" in d:
        d["pipeline_output"] = (
            None if d["pipeline_output"] is None else _jsonish_to_dict(d["pipeline_output"])
        )
    if "options" in d:
        d["options"] = _jsonish_to_dict(d["options"])
    return d


def _jsonish_to_dict(value: Any) -> dict[str, Any]:
    """Normalize a JSON-like DB field into a plain dict for API responses."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _datetime_to_iso(value: Any) -> str | None:
    """Normalize datetime-ish values to ISO 8601 strings for API responses."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value
    return str(value)


@staticmethod
def to_response(task: dict[str, Any]) -> TaskResponse:
    """Build a TaskResponse from a raw task dict (kept as static method)."""
    payload = {k: task.get(k) for k in TaskResponse.model_fields}
    payload["created_at"] = _datetime_to_iso(task.get("created_at")) or ""
    payload["completed_at"] = _datetime_to_iso(task.get("completed_at"))
    payload["options"] = _jsonish_to_dict(task.get("options"))
    pipeline_output = task.get("pipeline_output")
    if pipeline_output is not None:
        payload["pipeline_output"] = _jsonish_to_dict(pipeline_output)

    return TaskResponse(**payload)


# Attach static method to class for backward compatibility
TaskStore.to_response = to_response  # type: ignore[attr-defined]
