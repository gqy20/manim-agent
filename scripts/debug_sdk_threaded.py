"""Simulate pipeline's threaded environment to find why SDK stream cuts short.

Key difference from working debug_sdk_test.py:
- Runs query() inside a dedicated thread (like _run_pipeline_thread)
- Uses asyncio.run() for new event loop (Windows/Python 3.13 requirement)
"""

import asyncio
import json
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from claude_agent_sdk import (
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    query,
)


def build_options(cwd: str) -> ClaudeAgentOptions:
    out_dir = Path(cwd)
    out_dir.mkdir(parents=True, exist_ok=True)
    return ClaudeAgentOptions(
        cwd=cwd,
        system_prompt="You are a helpful assistant. Use tools to complete tasks.",
        permission_mode="bypassPermissions",
        max_turns=10,
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        output_format={
            "type": "json_schema",
            "schema": {
                "type": "object",
                "properties": {
                    "video_output": {"type": "string"},
                },
                "required": ["video_output"],
            },
        },
    )


def run_in_thread(prompt: str, options: ClaudeAgentOptions) -> dict:
    """Exact replica of _run_pipeline_thread logic."""
    result = {"error": None, "msg_count": 0, "msg_types": {}, "assistant_count": 0,
             "has_result": False, "result_data": None, "exception": None}

    def _inner():
        try:
            async def _main():
                count = 0
                types = {}
                acount = 0
                has_result = False
                result_data = None

                async for message in query(prompt=prompt, options=options):
                    count += 1
                    t = type(message).__name__
                    types[t] = types.get(t, 0) + 1

                    if isinstance(message, AssistantMessage):
                        acount += 1
                        blocks = message.content
                        print(f"  [T#{count} A#{acount}] stop_reason={message.stop_reason!r} "
                              f"blocks={len(blocks)}")
                        for b in blocks:
                            bt = type(b).__name__
                            if bt == "ToolUseBlock":
                                print(f"         {b.name}: {str(b.input)[:80]!r}")
                            elif bt == "TextBlock":
                                print(f"         Text: {b.text[:80]!r}")

                    elif isinstance(message, ResultMessage):
                        has_result = True
                        result_data = message.structured_output
                        print(f"  [T#{count}] RESULT: stop={message.stop_reason!r} "
                              f"turns={message.num_turns} error={message.is_error}")
                        if message.structured_output:
                            print(f"         structured_output={message.structured_output}")

                # After loop ends
                result["msg_count"] = count
                result["msg_types"] = types
                result["assistant_count"] = acount
                result["has_result"] = has_result
                result["result_data"] = result_data
                print(f"\n  [END] total={count} types={types} "
                      f"assistant={acount} has_result={has_result}")

            asyncio.run(_main())

        except Exception as exc:
            result["exception"] = f"{type(exc).__name__}: {exc}"
            import traceback
            result["traceback"] = traceback.format_exc()
            print(f"\n  [EXC] {result['exception']}")
            for line in result["traceback"].splitlines()[:20]:
                print(f"    {line}")

    t = threading.Thread(target=_inner, daemon=True)
    t.start()
    t.join(timeout=120)
    if t.is_alive():
        result["exception"] = "TIMEOUT: thread still alive after 120s"
    return result


# ── Test A: Direct (baseline - should work) ────────────────────────
print("=" * 60)
print("TEST A: Direct call (no thread)")
print("=" * 60)

out_dir_a = Path(__file__).parent / "backend" / "output" / "test_direct"
opts_a = build_options(str(out_dir_a))

direct_result = {}
async def _direct():
    count = 0
    types = {}
    acount = 0
    async for message in query(prompt="run pwd then write test.py with 'print(42)'",
                             options=opts_a):
        count += 1
        t = type(message).__name__
        types[t] = types.get(t, 0) + 1
        if isinstance(message, AssistantMessage):
            acount += 1
            for b in message.content:
                if type(b).__name__ == "ToolUseBlock":
                    print(f"  [A#{count}] ToolUse: {b.name}")
        elif isinstance(message, ResultMessage):
            direct_result["has_result"] = True
            direct_result["turns"] = message.num_turns
            print(f"  [A#{count}] RESULT: turns={message.num_turns}")
    direct_result["count"] = count
    direct_result["types"] = types
    direct_result["acount"] = acount

asyncio.run(_direct())
print(f"  A: count={direct_result['count']} types={direct_result['types']} "
      f"result={direct_result['has_result']}\n")

# ── Test B: Threaded (like pipeline) ───────────────────────────────────
print("=" * 60)
print("TEST B: Threaded call (like pipeline)")
print("=" * 60)

out_dir_b = Path(__file__).parent / "backend" / "output" / "test_threaded"
opts_b = build_options(str(out_dir_b))

threaded = run_in_thread("run pwd then write test.py with 'print(42)", opts_b)

print(f"\n  B: count={threaded['msg_count']} types={threaded['msg_types']} "
      f"assistant={threaded['assistant_count']} result={threaded['has_result']}")
if threaded.get("exception"):
    print(f"  B EXCEPTION: {threaded['exception']}")

# ── Comparison ─────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("COMPARISON")
print("=" * 60)
print(f"{'':<25} {'Direct (A)':<20} {'Threaded (B)':<20}")
print("-" * 65)
print(f"{'Total messages':<25} {direct_result['count']:<20} {threaded['msg_count']:<20}")
print(f"{'Assistant msgs':<25} {direct_result['acount']:<20} {threaded['assistant_count']:<20}")
print(f"{'ResultMessage':<25} {str(direct_result['has_result']):<20} {str(threaded['has_result']):<20}")
print(f"{'Exception':<25} {'None':<20} {(threaded.get('exception') or 'None'):<20}")
