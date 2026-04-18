"""Smoke test: create tasks and report pass/fail without waiting for completion.

Run with the backend already running:
    python scripts/run_smoke.py

Results are best viewed in the frontend at http://localhost:3147
"""

import argparse
import asyncio
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BACKEND_URL = "http://127.0.0.1:8471"

TASKS = [
    {
        "label": "勾股定理证明",
        "user_text": "用动画演示并严格证明勾股定理：先画一个直角三角形，然后分别以三条边为边长画正方形，通过面积关系得出 a² + b² = c²，最后给出一个具体的数值例子（如 3-4-5）验证结论。",
        "quality": "medium",
        "no_tts": True,
    },
    {
        "label": "光的折射",
        "user_text": "用动画演示光从空气射入水中的折射现象：从左侧射入一条红色光线，经过水面时发生弯折，用虚线标注法线、入射角和折射角，标注斯涅尔定律 n1 sinθ1 = n2 sinθ2，最后分别演示光从光密介质到光疏介质时发生全反射的边界条件。",
        "quality": "medium",
        "no_tts": True,
    },
    {
        "label": "二分查找",
        "user_text": "用动画演示二分查找算法在有序数组 [2, 5, 8, 12, 16, 23, 38, 56, 72, 91] 中查找目标值 23 的过程：逐步缩小搜索区间，每次取出中点并高亮当前搜索范围，排除的一半用灰色标注，直到找到目标时给出提示。",
        "quality": "medium",
        "no_tts": True,
    },
]


async def create_task(client: httpx.AsyncClient, label: str, **task_kwargs) -> dict:
    payload = {
        "user_text": task_kwargs["user_text"],
        "quality": task_kwargs.get("quality", "medium"),
        "no_tts": task_kwargs.get("no_tts", False),
        "voice_id": "female-tianmei",
        "model": "speech-2.8-hd",
        "preset": "educational",
        "bgm_enabled": False,
        "bgm_volume": 0.12,
        "target_duration_seconds": 60,
    }
    try:
        resp = await client.post(f"{BACKEND_URL}/api/tasks", json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        print(f"[{label}] created -> task_id={data['id']}")
        return {"label": label, "task_id": data["id"], "status": "submitted"}
    except Exception as exc:
        print(f"[{label}] FAILED to create: {exc}")
        return {"label": label, "task_id": None, "status": "error", "error": str(exc)}


async def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test – trigger tasks without waiting")
    parser.add_argument(
        "--tasks",
        choices=["all", "quick"],
        default="all",
        help="'all' runs every entry; 'quick' runs only no_tts tasks.",
    )
    args = parser.parse_args()

    tasks_to_run = TASKS
    if args.tasks == "quick":
        tasks_to_run = [t for t in TASKS if t.get("no_tts", False)]

    print(f"Smoke test: creating {len(tasks_to_run)} task(s) against {BACKEND_URL}")
    print("Watch progress at http://localhost:3147\n")

    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*[create_task(client, **t) for t in tasks_to_run])

    print("\nSummary:")
    for r in results:
        if r["task_id"]:
            print(f"  [{r['label']}] {r['task_id']}")
        else:
            print(f"  [{r['label']}] ERROR: {r.get('error')}")

    submitted = sum(1 for r in results if r["task_id"])
    print(f"\n{submitted}/{len(results)} task(s) submitted.")
    return 0 if submitted == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
