"""Delete tasks from PostgreSQL with an opt-in dry-run workflow.

Examples:
    python -m backend.delete_tasks --status failed
    python -m backend.delete_tasks --status failed --garbled --execute
    python -m backend.delete_tasks --ids abc12345 deadbeef --execute --delete-output
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.storage.r2_client import R2Client, is_r2_url, r2_object_key
from backend.task_store import _get_database_url

import asyncpg

_OUTPUT_ROOT = ROOT / "backend" / "output"
_GARBLE_REGEX = re.compile(r"(鈹|锟|�|[?？]{4,})")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preview or delete tasks from the PostgreSQL task store.",
    )
    parser.add_argument(
        "--status",
        action="append",
        choices=["pending", "running", "completed", "failed"],
        help="Match one or more task statuses.",
    )
    parser.add_argument(
        "--garbled",
        action="store_true",
        help="Only match tasks whose user_text looks garbled.",
    )
    parser.add_argument(
        "--ids",
        nargs="+",
        help="Delete only the specified task IDs.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Preview at most this many tasks in dry-run output.",
    )
    parser.add_argument(
        "--delete-output",
        action="store_true",
        help="Also delete backend/output/<task_id> directories after DB deletion.",
    )
    parser.add_argument(
        "--delete-r2",
        action="store_true",
        help="Also delete the canonical R2 video object for each deleted task.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete rows. Without this flag, the script only previews matches.",
    )
    return parser


def _garbled_sql_clause() -> str:
    return (
        "user_text ~ '(鈹|锟|�|[?？]{4,})'"
    )


def _preview_text(value: str, max_len: int = 48) -> str:
    compact = " ".join(value.split())
    if len(compact) <= max_len:
        return compact
    return f"{compact[: max_len - 3]}..."


def _looks_garbled(value: str) -> bool:
    return bool(_GARBLE_REGEX.search(value or ""))


async def _fetch_matches(
    conn: asyncpg.Connection,
    *,
    statuses: Sequence[str] | None,
    garbled_only: bool,
    ids: Sequence[str] | None,
) -> list[asyncpg.Record]:
    conditions: list[str] = []
    params: list[object] = []
    param_index = 1

    if statuses:
        conditions.append(f"status = ANY(${param_index}::text[])")
        params.append(list(statuses))
        param_index += 1

    if ids:
        conditions.append(f"id = ANY(${param_index}::text[])")
        params.append(list(ids))
        param_index += 1

    if garbled_only:
        conditions.append(_garbled_sql_clause())

    where_clause = " AND ".join(conditions) if conditions else "TRUE"
    query = f"""
        SELECT id, status, created_at, completed_at, user_text, video_path
        FROM tasks
        WHERE {where_clause}
        ORDER BY created_at DESC
    """
    return await conn.fetch(query, *params)


def _print_summary(rows: Sequence[asyncpg.Record], limit: int) -> None:
    print(f"Matched {len(rows)} task(s).")
    if not rows:
        return

    print("Preview:")
    for row in rows[:limit]:
        preview = _preview_text(row["user_text"] or "")
        garbled = "yes" if _looks_garbled(row["user_text"] or "") else "no"
        print(
            f"  {row['id']}  status={row['status']}  garbled={garbled}  "
            f"created={row['created_at']}  text={preview}"
        )

    if len(rows) > limit:
        print(f"  ... and {len(rows) - limit} more")


def _delete_output_dirs(task_ids: Sequence[str]) -> None:
    for task_id in task_ids:
        output_dir = _OUTPUT_ROOT / task_id
        if output_dir.exists():
            shutil.rmtree(output_dir, ignore_errors=True)


def _delete_r2_objects(task_ids: Sequence[str]) -> None:
    client = R2Client.create()
    if client is None:
        print("R2 is not configured; skipped R2 deletion.")
        return

    for task_id in task_ids:
        client.delete_object(r2_object_key(task_id))


async def _run(args: argparse.Namespace) -> int:
    load_dotenv(ROOT / ".env")
    _get_database_url()

    if not any([args.status, args.garbled, args.ids]):
        print("Refusing to run without filters. Use --status, --garbled, or --ids.")
        return 2

    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        rows = await _fetch_matches(
            conn,
            statuses=args.status,
            garbled_only=args.garbled,
            ids=args.ids,
        )
        _print_summary(rows, args.limit)

        if not args.execute:
            print("\nDry run only. Add --execute to delete these tasks.")
            return 0

        if not rows:
            print("\nNothing to delete.")
            return 0

        task_ids = [row["id"] for row in rows]
        await conn.execute("DELETE FROM tasks WHERE id = ANY($1::text[])", task_ids)
        print(f"\nDeleted {len(task_ids)} task row(s) from PostgreSQL.")

        if args.delete_output:
            _delete_output_dirs(task_ids)
            print("Deleted matching backend/output directories.")

        if args.delete_r2:
            _delete_r2_objects(task_ids)
            print("Requested deletion of matching R2 video objects.")

        return 0
    finally:
        await conn.close()


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
