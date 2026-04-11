"""Utility to clean stale backend tasks in the PostgreSQL task table."""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.task_store import TaskStore, _get_database_url
from backend.models import TaskStatus


async def main() -> None:
    parser = argparse.ArgumentParser(description="Clean stale backend tasks from DB.")
    parser.add_argument(
        "--include-pending",
        action="store_true",
        help="Also mark pending tasks as failed.",
    )
    parser.add_argument(
        "--set-error",
        default="Manually cleaned during maintenance.",
        help="Error message to store when forcing failed state.",
    )
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    _get_database_url()

    store = TaskStore()
    await store.start()

    try:
        async with store.pool.acquire() as conn:
            if args.include_pending:
                statuses = (TaskStatus.RUNNING.value, TaskStatus.PENDING.value)
            else:
                statuses = (TaskStatus.RUNNING.value,)

            query_statuses = ", ".join(f"'{s}'" for s in statuses)
            rows = await conn.fetch(
                f"SELECT id, status FROM tasks WHERE status IN ({query_statuses})"
            )
            task_ids = [row["id"] for row in rows]
            if not task_ids:
                print("No stale tasks found.")
                return

            now = datetime.now(timezone.utc)
            result = await conn.execute(
                f"""
                UPDATE tasks
                SET
                    status = $1,
                    error = $2,
                    completed_at = $3,
                    updated_at = $3
                WHERE status IN ({query_statuses})
                """,
                TaskStatus.FAILED.value,
                args.set_error,
                now,
            )
            updated = int(result.split()[-1])
            print(f"Updated {updated} tasks to failed.")
            print("Task IDs:")
            print("\n".join(task_ids))

            output_root = ROOT / "backend" / "output"
            for task_id in task_ids:
                output_dir = output_root / task_id
                if output_dir.exists():
                    marker = output_dir / "_cleanup_marker.txt"
                    marker.write_text(
                        f"Task cleaned by maintenance at {now.isoformat()}",
                        encoding="utf-8",
                    )
    finally:
        await store.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as exc:
        raise SystemExit(str(exc))
