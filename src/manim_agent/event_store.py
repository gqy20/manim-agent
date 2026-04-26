"""SSE 事件持久化存储：append-only JSONL 文件 + 内存索引。

提供：
- EventStore：按 task_id 隔离的事件持久化
- append() / query() / count() / cleanup() / replay_for_sse()
- 基于 JSONL 的文件存储，支持跨实例恢复
- 线程安全（用于 async 场景时由调用方保证串行）
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Optional

from .pipeline_events import PipelineEvent

logger = logging.getLogger(__name__)


class EventStore:
    """按 task_id 隔离的 append-only 事件持久化。

    存储格式：每个 task 一个 .jsonl 文件，每行一个序列化 PipelineEvent。
    同时维护内存中的行数索引，避免全量扫描。
    """

    def __init__(self, store_dir: str | Path = "events") -> None:
        self._store_dir = Path(store_dir)
        self._store_dir.mkdir(parents=True, exist_ok=True)
        self._counts: dict[str, int] = {}
        self._lock = threading.Lock()

    def _task_file(self, task_id: str) -> Path:
        return self._store_dir / f"{task_id}.jsonl"

    def append(self, task_id: str, event: PipelineEvent) -> None:
        """追加一个事件到对应 task 的存储文件。"""
        path = self._task_file(task_id)
        serialized = event.model_dump_json(by_alias=True)
        with self._lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(serialized + "\n")
            self._counts[task_id] = self._counts.get(task_id, 0) + 1

    def count(self, task_id: str) -> int:
        """返回某 task 的事件总数（优先使用缓存，回退到文件扫描）。"""
        with self._lock:
            cached = self._counts.get(task_id)
            if cached is not None:
                return cached
            path = self._task_file(task_id)
            if not path.exists():
                return 0
            count = sum(1 for _ in open(path, encoding="utf-8"))
            self._counts[task_id] = count
            return count

    def query(
        self,
        task_id: str,
        *,
        event_type: Any = None,
        limit: int = 0,
        offset: int = 0,
    ) -> list[PipelineEvent]:
        """查询事件列表，支持类型过滤和分页。"""
        path = self._task_file(task_id)
        if not path.exists():
            return []

        results: list[PipelineEvent] = []
        skipped = 0
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = PipelineEvent.model_validate_json(line)
                except Exception as e:
                    logger.debug("event_store skip malformed line: %s", e)
                    continue

                if offset > 0 and skipped < offset:
                    skipped += 1
                    continue

                if event_type is not None and evt.event_type != event_type:
                    continue

                results.append(evt)

                if limit > 0 and len(results) >= limit:
                    break

        return results

    def cleanup(self, task_id: str) -> None:
        """删除某个 task 的所有事件数据。"""
        path = self._task_file(task_id)
        with self._lock:
            if path.exists():
                path.unlink()
            self._counts.pop(task_id, None)

    def replay_for_sse(
        self, task_id: str, *, limit: int = 500
    ) -> list[str]:
        """为 SSE 回放返回已序列化的 JSON 字符串列表（兼容 SSESubscriptionManager.push）。"""
        events = self.query(task_id, limit=limit)
        return [evt.model_dump_json(by_alias=True) for evt in events]
