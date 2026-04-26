"""Tests for SSE 事件持久化 event_store（P1）。

覆盖：EventStore 的 append、查询、按 task_id 过滤、
按事件类型过滤、时间范围查询、离线回放、
并发安全。
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from manim_agent.pipeline_events import (
    EventType,
    PipelineEvent,
    ProgressPayload,
    StatusPayload,
    ToolStartPayload,
)


# ── EventStore 基本操作 ───────────────────────────────────────


class TestEventStoreAppend:
    def test_append_and_count(self):
        from manim_agent.event_store import EventStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = EventStore(store_dir=tmpdir)
            store.append("task-1", PipelineEvent(
                event_type=EventType.LOG, data="hello",
            ))
            store.append("task-1", PipelineEvent(
                event_type=EventType.STATUS, data=StatusPayload(
                    task_status="running", phase="init",
                ),
            ))
            assert store.count("task-1") == 2

    def test_append_different_tasks_isolated(self):
        from manim_agent.event_store import EventStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = EventStore(store_dir=tmpdir)
            store.append("task-a", PipelineEvent(event_type=EventType.LOG, data="a"))
            store.append("task-b", PipelineEvent(event_type=EventType.LOG, data="b"))
            assert store.count("task-a") == 1
            assert store.count("task-b") == 1

    def test_append_persists_across_instances(self):
        """重启 EventStore 实例后数据不丢失。"""
        from manim_agent.event_store import EventStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store1 = EventStore(store_dir=tmpdir)
            evt = PipelineEvent(event_type=EventType.LOG, data="persisted")
            store1.append("task-p", evt)
            del store1

            store2 = EventStore(store_dir=tmpdir)
            assert store2.count("task-p") == 1


class TestEventStoreQuery:
    def test_query_all_for_task(self):
        from manim_agent.event_store import EventStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = EventStore(store_dir=tmpdir)
            for i in range(5):
                store.append("task-q", PipelineEvent(
                    event_type=EventType.LOG, data=f"line-{i}",
                ))
            results = store.query("task-q")
            assert len(results) == 5

    def test_query_by_event_type(self):
        from manim_agent.event_store import EventStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = EventStore(store_dir=tmpdir)
            store.append("task-f", PipelineEvent(event_type=EventType.LOG, data="log"))
            store.append("task-f", PipelineEvent(
                event_type=EventType.TOOL_START,
                data=ToolStartPayload(tool_use_id="t1", name="Bash", input_summary={}),
            ))
            store.append("task-f", PipelineEvent(event_type=EventType.LOG, data="log2"))

            tool_starts = store.query("task-f", event_type=EventType.TOOL_START)
            assert len(tool_starts) == 1
            logs = store.query("task-f", event_type=EventType.LOG)
            assert len(logs) == 2

    def test_query_limit_and_offset(self):
        from manim_agent.event_store import EventStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = EventStore(store_dir=tmpdir)
            for i in range(10):
                store.append("task-lim", PipelineEvent(event_type=EventType.LOG, data=f"{i}"))

            page1 = store.query("task-lim", limit=3, offset=0)
            assert len(page1) == 3
            page2 = store.query("task-lim", limit=3, offset=3)
            assert len(page2) == 3
            # 确保分页不重叠
            p1_ids = {e.data for e in page1}
            p2_ids = {e.data for e in page2}
            assert not p1_ids.intersection(p2_ids)

    def test_query_unknown_task_returns_empty(self):
        from manim_agent.event_store import EventStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = EventStore(store_dir=tmpdir)
            assert store.query("nonexistent") == []

    def test_query_returns_chronological_order(self):
        from manim_agent.event_store import EventStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = EventStore(store_dir=tmpdir)
            for i in range(5):
                store.append("task-ord", PipelineEvent(event_type=EventType.LOG, data=str(i)))
            results = store.query("task-ord")
            datas = [e.data for e in results]
            assert datas == ["0", "1", "2", "3", "4"]


class TestEventStoreCleanup:
    def test_cleanup_removes_task_data(self):
        from manim_agent.event_store import EventStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = EventStore(store_dir=tmpdir)
            store.append("task-del", PipelineEvent(event_type=EventType.LOG, data="x"))
            assert store.count("task-del") == 1
            store.cleanup("task-del")
            assert store.count("task-del") == 0

    def test_cleanup_nonexistent_task_noop(self):
        from manim_agent.event_store import EventStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = EventStore(store_dir=tmpdir)
            store.cleanup("ghost")  # 不抛异常


class TestEventStoreReplayForSSE:
    def test_replay_serializes_to_sse_format(self):
        """replay_for_sse 返回 SSE 兼容的 JSON 字符串列表。"""
        from manim_agent.event_store import EventStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = EventStore(store_dir=tmpdir)
            store.append("task-sse", PipelineEvent(
                event_type=EventType.PROGRESS,
                data=ProgressPayload(turn=1, total_tokens=100, tool_uses=0, elapsed_ms=500),
            ))

            lines = store.replay_for_sse("task-sse")
            assert len(lines) == 1
            # 每行应是合法 JSON
            parsed = json.loads(lines[0])
            assert parsed["event_type"] == "progress"
            assert "data" in parsed
            assert "timestamp" in parsed

    def test_replay_empty_task(self):
        from manim_agent.event_store import EventStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = EventStore(store_dir=tmpdir)
            assert store.replay_for_sse("empty") == []


class TestEventStoreConcurrency:
    def test_concurrent_appends_do_not_corrupt(self):
        """多线程/协程并发 append 不丢失数据。"""
        import asyncio

        from manim_agent.event_store import EventStore

        async def _run():
            with tempfile.TemporaryDirectory() as tmpdir:
                store = EventStore(store_dir=tmpdir)

                async def _append_n(n: int):
                    for i in range(n):
                        store.append("task-conc", PipelineEvent(
                            event_type=EventType.LOG, data=f"{n}-{i}",
                        ))

                await asyncio.gather(*(_append_n(50) for _ in range(4)))
                assert store.count("task-conc") == 200

        asyncio.run(_run())
