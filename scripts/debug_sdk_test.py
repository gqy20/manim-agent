"""Minimal script to reproduce SDK vs CLI behavior difference.

Run: uv run python debug_sdk_test.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from claude_agent_sdk import (
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    query,
)


async def main():
    prompt = "run pwd, then write a file called test_debug.py with content 'print(42)', do NOT render anything"

    out_dir = Path(__file__).parent / "backend" / "output" / "debug_test"
    out_dir.mkdir(parents=True, exist_ok=True)

    options = ClaudeAgentOptions(
        cwd=str(out_dir),
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

    print("=" * 60)
    print("SDK DEBUG TEST")
    print("=" * 60)
    print(f"prompt: {prompt!r}")
    print(f"cwd: {options.cwd}")
    print(f"allowed_tools: {options.allowed_tools}")
    print(f"has output_format: {options.output_format is not None}")
    print()

    msg_count = 0
    msg_types = {}
    assistant_count = 0

    try:
        async for message in query(prompt=prompt, options=options):
            msg_count += 1
            t = type(message).__name__
            msg_types[t] = msg_types.get(t, 0) + 1

            if isinstance(message, AssistantMessage):
                assistant_count += 1
                blocks = message.content
                print(f"[#{msg_count}] AssistantMessage #{assistant_count}: "
                      f"stop_reason={message.stop_reason!r}, "
                      f"blocks={len(blocks)}")
                for b in blocks:
                    bt = type(b).__name__
                    if bt == "ToolUseBlock":
                        print(f"       -> ToolUse: {b.name} input={str(b.input)[:100]!r}")
                    elif bt == "TextBlock":
                        print(f"       -> Text: {b.text[:100]!r}")
                    elif bt == "ThinkingBlock":
                        print(f"       -> Thinking: {b.thinking[:80]!r}")

            elif isinstance(message, ResultMessage):
                print(f"[#{msg_count}] ResultMessage: stop_reason={message.stop_reason!r}, "
                      f"is_error={message.is_error}, turns={message.num_turns}")
                if message.structured_output:
                    print(f"       structured_output={message.structured_output!r}")
                if message.errors:
                    print(f"       errors={message.errors}")
            else:
                print(f"[#{msg_count}] {t}")

    except Exception as exc:
        print(f"\n!!! EXCEPTION in query() loop: {type(exc).__name__}: {exc}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 60)
    print(f"STREAM ENDED")
    print(f"Total messages: {msg_count}")
    print(f"Types: {msg_types}")
    print(f"Assistant messages: {assistant_count}")
    print(f"ResultMessage received: {'ResultMessage' in msg_types}")


if __name__ == "__main__":
    asyncio.run(main())
