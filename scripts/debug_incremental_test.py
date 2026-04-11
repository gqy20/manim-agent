"""Incremental test: add one pipeline-specific factor at a time to isolate root cause.

Test matrix:
  A: Simple prompt + json_schema (baseline - already known to work)
  B: Simple prompt + json_schema + hooks (PostToolUse)
  C: Simple prompt + json_schema + enable_file_checkpointing
  D: Full manim system prompt + json_schema (no hooks, no checkpointing)
  E: Full manim system prompt + json_schema + hooks
  F: Full manim system prompt + json_schema + hooks + checkpointing + fork_session (exact pipeline replica)

Run: uv run python debug_incremental_test.py
"""

import asyncio
import functools
import json
import os
import sys
import threading
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
from manim_agent.__main__ import _on_post_tool_use

# ── Shared helpers ──────────────────────────────────────────────


def make_output_dir(name: str) -> Path:
    out = Path(__file__).parent / "backend" / "output" / f"test_inc_{name}"
    out.mkdir(parents=True, exist_ok=True)
    return out


def run_test(label: str, options: ClaudeAgentOptions, prompt: str, timeout: int = 180) -> dict:
    """Run a single test in a thread (like real pipeline)."""
    result = {
        "label": label,
        "msg_count": 0,
        "msg_types": {},
        "assistant_count": 0,
        "has_result": False,
        "result_data": None,
        "stop_reasons": [],
        "tool_names": [],
        "exception": None,
        "text_blocks": 0,
    }

    def _inner():
        try:
            async def _main():
                async for message in query(prompt=prompt, options=options):
                    result["msg_count"] += 1
                    t = type(message).__name__
                    result["msg_types"][t] = result["msg_types"].get(t, 0) + 1

                    if isinstance(message, AssistantMessage):
                        result["assistant_count"] += 1
                        result["stop_reasons"].append(str(message.stop_reason))
                        for b in message.content:
                            bt = type(b).__name__
                            if bt == "ToolUseBlock":
                                result["tool_names"].append(b.name)
                            elif bt == "TextBlock":
                                result["text_blocks"] += 1

                    elif isinstance(message, ResultMessage):
                        result["has_result"] = True
                        result["result_data"] = message.structured_output

            asyncio.run(_main())

        except Exception as exc:
            result["exception"] = f"{type(exc).__name__}: {exc}"

    t = threading.Thread(target=_inner, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        result["exception"] = "TIMEOUT"

    return result


def print_result(r: dict) -> str:
    """Return verdict string."""
    status = "PASS" if r["has_result"] else "FAIL"
    exc = f" [EXC: {r['exception'][:60]}]" if r.get("exception") else ""
    return (
        f"  {status}{exc}\n"
        f"    msgs={r['msg_count']} types={r['msg_types']} "
        f"asst={r['assistant_count']} result={r['has_result']}\n"
        f"    stops={r['stop_reasons']}\n"
        f"    tools={r['tool_names']}\n"
        f"    text_blks={r['text_blocks']}"
    )


# ── Build option variants ────────────────────────────────────────


def opts_simple(cwd: str) -> ClaudeAgentOptions:
    """Baseline: simple prompt, json_schema only."""
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
                "properties": {"video_output": {"type": "string"}},
                "required": ["video_output"],
            },
        },
    )


def opts_with_hooks(cwd: str) -> ClaudeAgentOptions:
    """B: Simple prompt + hooks."""
    o = opts_simple(cwd)
    # Can't mutate frozen dataclass, rebuild
    return ClaudeAgentOptions(
        cwd=o.cwd,
        system_prompt=o.system_prompt,
        permission_mode=o.permission_mode,
        max_turns=o.max_turns,
        allowed_tools=o.allowed_tools,
        output_format=o.output_format,
        hooks={
            "PostToolUse": [
                HookMatcher(
                    matcher="Write|Edit",
                    hooks=[_on_post_tool_use],
                ),
            ],
        },
    )


def opts_with_checkpointing(cwd: str) -> ClaudeAgentOptions:
    """C: Simple prompt + file checkpointing."""
    o = opts_simple(cwd)
    return ClaudeAgentOptions(
        cwd=o.cwd,
        system_prompt=o.system_prompt,
        permission_mode=o.permission_mode,
        max_turns=o.max_turns,
        allowed_tools=o.allowed_tools,
        output_format=o.output_format,
        enable_file_checkpointing=True,
    )


def opts_full_prompt(cwd: str, quality: str = "low") -> ClaudeAgentOptions:
    """D/E/F variants: full manim system prompt."""
    full_system = prompts.get_prompt(user_text="", preset="default", quality=quality)
    system_prompt = full_system.rsplit("\n\n# 用户需求", 1)[0]

    venv_scripts = str(Path(__file__).parent.parent / ".venv" / "Scripts")
    current_path = os.environ.get("PATH", "")
    path_parts = [p for p in current_path.split(os.pathsep) if p]
    if venv_scripts not in path_parts:
        path_parts.append(venv_scripts)
    venv_env = {"PATH": os.pathsep.join(path_parts)}

    return ClaudeAgentOptions(
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
        env=venv_env,
        session_id=str(uuid.uuid4()),
        fork_session=False,  # Will add in F
        enable_file_checkpointing=False,  # Will add in E/F
        hooks=None,  # Will add in E/F
    )


def opts_full_prompt_hooks(cwd: str) -> ClaudeAgentOptions:
    """E: Full prompt + hooks."""
    o = opts_full_prompt(cwd)
    return ClaudeAgentOptions(
        cwd=o.cwd,
        system_prompt=o.system_prompt,
        permission_mode=o.permission_mode,
        max_turns=o.max_turns,
        allowed_tools=o.allowed_tools,
        output_format=o.output_format,
        env=o.env,
        session_id=o.session_id,
        fork_session=o.fork_session,
        enable_file_checkpointing=True,
        hooks={
            "PostToolUse": [
                HookMatcher(
                    matcher="Write|Edit",
                    hooks=[_on_post_tool_use],
                ),
            ],
        },
    )


def opts_exact_pipeline(cwd: str) -> ClaudeAgentOptions:
    """F: Exact replica of pipeline options."""
    o = opts_full_prompt(cwd)
    return ClaudeAgentOptions(
        cwd=o.cwd,
        system_prompt=o.system_prompt,
        permission_mode=o.permission_mode,
        max_turns=o.max_turns,
        allowed_tools=o.allowed_tools,
        output_format=o.output_format,
        env=o.env,
        session_id=o.session_id,
        fork_session=True,
        enable_file_checkpointing=True,
        hooks={
            "PostToolUse": [
                HookMatcher(
                    matcher="Write|Edit",
                    hooks=[_on_post_tool_use],
                ),
            ],
        },
    )


# ── Test runner ──────────────────────────────────────────────────

PROMPT_SIMPLE = (
    "run pwd, then write a file called test.py with content 'print(42)', "
    "do NOT render anything"
)

PROMPT_MANIM = (
    "draw a simple right triangle animation using manim, "
    "write the code to pythagorean.py, render it with manim -ql, "
    "then output VIDEO_OUTPUT"
)

TESTS = [
    ("A_baseline", opts_simple, PROMPT_SIMPLE),
    ("B_hooks", opts_with_hooks, PROMPT_SIMPLE),
    ("C_checkpointing", opts_with_checkpointing, PROMPT_SIMPLE),
    ("D_full_prompt", opts_full_prompt, PROMPT_SIMPLE),
    ("E_full_prompt_hooks", opts_full_prompt_hooks, PROMPT_SIMPLE),
    ("F_exact_pipeline", opts_exact_pipeline, PROMPT_MANIM),
]


def main():
    print("=" * 70)
    print("INCREMENTAL ROOT CAUSE ISOLATION TEST")
    print(f"Prompt (A-E): {PROMPT_SIMPLE!r}")
    print(f"Prompt (F):   {PROMPT_MANIM!r}")
    print("=" * 70)

    results = []
    for label, opts_fn, prompt in TESTS:
        print(f"\n--- Test {label} ---")
        out_dir = make_output_dir(label)
        opts = opts_fn(str(out_dir))
        print(f"  cwd={out_dir}")
        print(f"  sysprompt_len={len(opts.system_prompt) if opts.system_prompt else 0}")
        print(f"  hooks={'set' if opts.hooks else 'None'}")
        print(f"  checkpointing={opts.enable_file_checkpointing}")
        print(f"  fork_session={opts.fork_session}")

        r = run_test(label, opts, prompt)
        results.append((label, r))
        print(print_result(r))

    # ── Summary table ────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"{'Test':<20} {'Status':<8} {'Msgs':<6} {'Asst':<5} {'Result':<8} {'StopReasons':<30}")
    print("-" * 77)
    for label, r in results:
        status = "PASS" if r["has_result"] else "FAIL"
        stops = ", ".join(r["stop_reasons"][:3])
        if len(stops) > 28:
            stops = stops[:25] + "..."
        print(f"{label:<20} {status:<8} {r['msg_count']:<6} {r['assistant_count']:<5} "
              f"{str(r['has_result']):<8} {stops:<30}")

    # Identify transition point
    print("\n--- Transition Analysis ---")
    prev_pass = True
    for label, r in results:
        cur_pass = r["has_result"]
        if prev_pass and not cur_pass:
            print(f"  *** FIRST FAILURE at {label} ***")
            print(f"      Previous test passed, this one failed.")
            print(f"      The factor added in {label} is likely the root cause.")
        prev_pass = cur_pass


if __name__ == "__main__":
    main()
