"""Simulate exact web backend environment: main loop + threaded pipeline + callbacks.

This test replicates the EXACT execution context of routes.py:_run_pipeline_thread:
1. Main asyncio event loop (like uvicorn's loop)
2. log_callback using call_soon_threadsafe (cross-thread scheduling)
3. event_callback for structured events
4. Pipeline in dedicated thread with asyncio.run()
5. Full pipeline options (hooks, checkpointing, fork_session, manim prompt)

Run: uv run python debug_webenv_test.py
"""

import asyncio
import functools
import json
import os
import sys
import threading
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from claude_agent_sdk import (
    ClaudeAgentOptions,
    HookMatcher,
    AssistantMessage,
    ResultMessage,
    query,
)
from manim_agent import prompts
from manim_agent.__main__ import _on_post_tool_use, _build_options, run_pipeline


# ── Simulate web backend environment ─────────────────────────────


class SimulatedBackend:
    """Represents the uvicorn/FastAPI backend environment."""

    def __init__(self):
        self.loop: asyncio.AbstractEventLoop | None = None
        self.log_lines: list[str] = []
        self.events: list[dict] = []
        self.pipeline_result: dict | None = None
        self.pipeline_error: str | None = None

    def _safe_schedule(self, coro_factory) -> None:
        """Exact replica of routes.py._safe_schedule."""
        try:
            self.loop.call_soon_threadsafe(lambda: asyncio.create_task(coro_factory()))
        except RuntimeError:
            pass

    def make_log_callback(self, task_id: str):
        """Exact replica of routes.py log_callback closure."""
        def log_callback(line: str) -> None:
            self._safe_schedule(lambda ln=line: self._append_log(task_id, ln))
            try:
                self.loop.call_soon_threadsafe(self._sse_push, task_id, line)
            except RuntimeError:
                pass
        return log_callback

    def make_event_callback(self, task_id: str):
        """Exact replica of routes.py event_callback closure."""
        def event_callback(event) -> None:
            try:
                self.loop.call_soon_threadsafe(self._sse_push, task_id, event)
            except RuntimeError:
                pass
        return event_callback

    async def _append_log(self, task_id: str, line: str) -> None:
        self.log_lines.append(line)

    def _sse_push(self, task_id: str, data) -> None:
        self.events.append({"task_id": task_id, "data": data})

    def _run_pipeline_thread(self, task_id: str, user_text: str, output_dir: str):
        """Exact replica of routes.py._run_pipeline_thread."""
        import asyncio as _asyncio

        log_callback = self.make_log_callback(task_id)
        event_callback = self.make_event_callback(task_id)

        log_callback("[SYS] Connecting to Claude Agent SDK...")
        self._safe_schedule(
            lambda: self._update_status(task_id, "RUNNING")
        )

        dispatcher_ref: list = []
        try:
            full_system_prompt = prompts.get_prompt(
                user_text="", preset="default", quality="low"
            )
            system_prompt = full_system_prompt.rsplit("\n\n# 用户需求", 1)[0]

            final_video = _asyncio.run(
                run_pipeline(
                    user_text=user_text,
                    output_path=str(Path(output_dir) / "final.mp4"),
                    voice_id="female-tianmei",
                    model="speech-2.8-hd",
                    quality="low",
                    no_tts=True,
                    cwd=output_dir,
                    max_turns=50,
                    log_callback=log_callback,
                    preset="default",
                    _dispatcher_ref=dispatcher_ref,
                    event_callback=event_callback,
                )
            )
            self.pipeline_result = {
                "video_path": final_video,
                "status": "COMPLETED",
            }
            po_data = None
            if dispatcher_ref:
                dispatcher = dispatcher_ref[0]
                po = dispatcher.get_pipeline_output()
                if po is not None:
                    po_data = po.model_dump()
            self.pipeline_result["pipeline_output"] = po_data

            self._safe_schedule(
                lambda: self._update_status(task_id, "COMPLETED")
            )
        except Exception as exc:
            error_message = f"{type(exc).__name__}: {exc}"
            self.pipeline_error = error_message
            log_callback(f"[ERR] {error_message}")
            import traceback as tb
            for line in tb.format_exception(type(exc), exc, exc.__traceback__):
                for ll in line.rstrip().splitlines():
                    log_callback(f"[TRACE] {ll}")
            self._safe_schedule(
                lambda: self._update_status(task_id, "FAILED")
            )
        finally:
            try:
                self.loop.call_soon_threadsafe(self._sse_done, task_id)
            except RuntimeError:
                pass

    async def _update_status(self, task_id: str, status: str) -> None:
        pass  # Simplified - just track via events

    def _sse_done(self, task_id: str) -> None:
        self.events.append({"task_id": task_id, "type": "done"})

    async def run_test(self, task_id: str, user_text: str, output_dir: str):
        """Run the full simulated backend test."""
        self.loop = asyncio.get_running_loop()

        # Start pipeline in background thread (exact replica of routes.py)
        thread = threading.Thread(
            target=self._run_pipeline_thread,
            args=(task_id, user_text, output_dir),
            daemon=True,
        )
        thread.start()

        # Wait for pipeline to complete (with timeout)
        timeout = 300  # 5 minutes
        start = time.time()
        while thread.is_alive():
            await asyncio.sleep(0.5)
            if time.time() - start > timeout:
                return {"error": "TIMEOUT: pipeline thread still alive"}

        # Small delay to let pending callbacks flush
        await asyncio.sleep(0.5)

        return {
            "pipeline_result": self.pipeline_result,
            "pipeline_error": self.pipeline_error,
            "log_count": len(self.log_lines),
            "event_count": len(self.events),
            "log_tail": self.log_lines[-20:] if self.log_lines else [],
            "event_tail": self.events[-10:] if self.events else [],
        }


# ── Main ─────────────────────────────────────────────────────────


async def main():
    print("=" * 70)
    print("WEB BACKEND ENVIRONMENT SIMULATION TEST")
    print("=" * 70)

    task_id = f"test-webenv-{uuid.uuid4().hex[:8]}"
    out_dir = Path(__file__).parent / "backend" / "output" / task_id
    out_dir.mkdir(parents=True, exist_ok=True)

    prompt = (
        "draw a simple right triangle animation using manim, "
        "write the code to pythagorean.py, render it with manim -ql, "
        "then output VIDEO_OUTPUT"
    )

    print(f"Task ID: {task_id}")
    print(f"Output dir: {out_dir}")
    print(f"Prompt: {prompt!r}")
    print()

    backend = SimulatedBackend()
    result = await backend.run_test(task_id, prompt, str(out_dir))

    print("\n--- RESULT ---")
    print(f"Pipeline result: {result.get('pipeline_result')}")
    print(f"Pipeline error: {result.get('pipeline_error')}")
    print(f"Log lines captured: {result.get('log_count')}")
    print(f"Events captured: {result.get('event_count')}")

    if result.get("log_tail"):
        print(f"\n--- Last 20 log lines ---")
        for line in result["log_tail"]:
            print(f"  {line}")

    if result.get("event_tail"):
        print(f"\n--- Last 10 events ---")
        for ev in result["event_tail"]:
            print(f"  {ev}")

    # Verdict
    pr = result.get("pipeline_result", {})
    if pr and pr.get("status") == "COMPLETED":
        print("\n=== PASS: Pipeline completed successfully ===")
    elif result.get("pipeline_error"):
        print(f"\n=== FAIL: {result['pipeline_error']} ===")
    else:
        print(f"\n=== UNKNOWN: {result} ===")


if __name__ == "__main__":
    asyncio.run(main())
