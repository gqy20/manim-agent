import pytest

from manim_agent.hooks import _on_pre_tool_use


async def _call_pre_tool_use(tool_name: str, tool_input: dict, cwd: str):
    result = await _on_pre_tool_use(
        {
            "tool_name": tool_name,
            "tool_input": tool_input,
            "cwd": cwd,
        },
        tool_use_id="tu_001",
        context={},
    )
    return result


class TestHookTaskScope:
    @pytest.mark.asyncio
    async def test_write_denial_includes_relative_retry_hint(self):
        result = await _call_pre_tool_use(
            "Write",
            {"file_path": r"D:\root\circle_to_square.py", "content": "print('x')"},
            r"D:\repo\backend\output\task-1",
        )

        assert result["decision"] == "block"
        reason = result["reason"]
        assert "Rejected path" in reason
        assert "`scene.py`" in reason
        assert "relative path inside the task directory" in reason

    @pytest.mark.asyncio
    async def test_bash_denial_includes_direct_manim_retry_hint(self):
        result = await _call_pre_tool_use(
            "Bash",
            {"command": r"D:\manim-agent\.venv\Scripts\python -m manim scene.py GeneratedScene"},
            r"D:\manim-agent\backend\output\task-1",
        )

        assert result["decision"] == "block"
        reason = result["reason"]
        assert "Rejected path" in reason
        assert "manim -qh scene.py GeneratedScene" in reason
        assert "do not invoke `.venv/Scripts/python`".lower() in reason.lower()

    @pytest.mark.asyncio
    async def test_in_scope_write_is_allowed(self):
        result = await _call_pre_tool_use(
            "Write",
            {"file_path": r"D:\repo\backend\output\task-1\scene.py", "content": "print('x')"},
            r"D:\repo\backend\output\task-1",
        )

        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"
