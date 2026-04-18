from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

import asyncpg
import pytest

from backend.task_store import TaskStore


class TestTaskStoreLogging:
    @pytest.mark.asyncio
    async def test_start_logs_pool_ready(self, monkeypatch, caplog):
        monkeypatch.setenv("DATABASE_URL", "postgres://example")
        fake_pool = AsyncMock()

        with (
            patch("backend.task_store.asyncpg.create_pool", new=AsyncMock(return_value=fake_pool)),
            patch.object(TaskStore, "_ensure_status_constraint", new=AsyncMock()),
            caplog.at_level(logging.INFO),
        ):
            store = TaskStore()
            await store.start()

        record = next(record for record in caplog.records if record.msg == "task_store_pool_started")
        assert record.min_size == 2
        assert record.max_size == 10

    @pytest.mark.asyncio
    async def test_run_with_retry_logs_retry_and_exhaustion(self, caplog):
        store = TaskStore()

        async def _failing():
            raise asyncpg.InterfaceError("db down")

        with caplog.at_level(logging.WARNING), pytest.raises(asyncpg.InterfaceError):
            await store._run_with_retry("update_status[task-1]", _failing, attempts=2, base_delay=0)

        retry = next(record for record in caplog.records if record.msg == "task_store_retry")
        assert retry.operation == "update_status[task-1]"
        exhausted = next(record for record in caplog.records if record.msg == "task_store_retry_exhausted")
        assert exhausted.operation == "update_status[task-1]"
