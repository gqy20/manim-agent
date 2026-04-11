"""Test with exact pipeline options (long system prompt, manim context)."""

import asyncio
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
from manim_agent import prompts


async def test_pipeline_style(prompt: str, cwd: str) -> dict:
    full_system = prompts.get_prompt(user_text="", preset="default", quality="low")
    system_prompt = full_system.rsplit("\n\n# 用户需求", 1)[0]

    out_dir = Path(cwd)
    out_dir.mkdir(parents=True, exist_ok=True)

    options = ClaudeAgentOptions(
        cwd=cwd,
        system_prompt=system_prompt,
        permission_mode="bypassPermissions",
        max_turns=10,
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        output_format={
            "type": "json_schema",
            "schema": {
                "type": "object",
                "properties": {"video_output": {"type": "string"}},
                "required": ["video_output"],
            },
        },
        hooks={"PostToolUse": []},
        enable_file_checkpointing=True,
    )

    result = {"count": 0, "types": {}, "acount": 0,
             "has_result": False, "result_data": None, "exc": None}

    async def _main():
        try:
            async for message in query(prompt=prompt, options=options):
                result["count"] += 1
                t = type(message).__name__
                result["types"][t] = result["types"].get(t, 0) + 1

                if isinstance(message, AssistantMessage):
                    result["acount"] += 1
                    blocks = message.content
                    print(f"  [#{result['count']} A#{result['acount']}] "
                          f"stop={message.stop_reason!r} blks={len(blocks)}")
                    for b in blocks:
                        bt = type(b).__name__
                        if bt == "ToolUseBlock":
                            print(f"       {b.name}: {str(b.input)[:100]!r}")
                        elif bt == "TextBlock":
                            print(f"       Text: {b.text[:100]!r}")

                elif isinstance(message, ResultMessage):
                    result["has_result"] = True
                    result["result_data"] = message.structured_output
                    print(f"  [#{result['count']}] RESULT: stop={message.stop_reason!r} "
                          f"turns={message.num_turns} err={message.is_error}")
                    if message.structured_output:
                        print(f"         so={message.structured_output}")

            print(f"\n  [END] count={result['count']} types={result['types']} "
                  f"a_count={result['acount']} has_result={result['has_result']}")

        except Exception as exc:
            result["exc"] = f"{type(exc).__name__}: {exc}"
            import traceback as tb
            for line in tb.format_exc()[:15]:
                print(f"    {line}")

    asyncio.run(_main())
    return result


out_dir = Path(__file__).parent / "backend" / "output" / "test_pipe"
prompt = (
    "draw a simple right triangle animation using manim, "
    "write the code to pythagorean.py, render it with manim -ql, "
    "then output VIDEO_OUTPUT"
)

print("=" * 60)
print("PIPELINE-STYLE TEST (threaded, full prompt)")
print(f"prompt: {prompt!r}")
print(f"cwd: {out_dir}")
print("=" * 60)

t = threading.Thread(
    target=lambda: asyncio.run(test_pipeline_style(prompt, str(out_dir))),
    daemon=True,
)
t.start()
t.join(timeout=180)

if t.is_alive():
    print("TIMEOUT")
else:
    print("\nDone.")
