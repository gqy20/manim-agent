"""SDK Hook 回调：捕获 Write/Edit 工具的源码。"""

import logging

from claude_agent_sdk.types import (
    PostToolUseHookSpecificOutput,
    SyncHookJSONOutput,
)

logger = logging.getLogger(__name__)


class _HookState:
    """Hook 共享状态，用于在多个 hook 调用间传递数据。"""

    def __init__(self) -> None:
        self.captured_source_code: dict[str, str] = {}
        self.event_callback = None


_hook_state = _HookState()


async def _on_post_tool_use(
    input_data,
    tool_use_id: str | None,
    context,
) -> SyncHookJSONOutput:
    """PostToolUse hook：捕获 Write/Edit 工具的源码。

    使用 SDK 原生 Hook 系统替代手动遍历 ToolUseBlock。
    """
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    logger.debug(
        "PostToolUse: tool_name=%r, tool_use_id=%r",
        tool_name, tool_use_id,
    )

    if tool_name in ("Write", "Edit") and isinstance(tool_input, dict):
        file_path = tool_input.get("file_path", "")
        content = tool_input.get("content", "")
        logger.debug(
            "PostToolUse: %s file_path=%r, content_length=%s",
            tool_name, file_path, len(content) if content else 0,
        )
        if file_path.endswith(".py") and content:
            _hook_state.captured_source_code[file_path] = content
            logger.debug(
                "Captured source: %s, total_files=%d",
                file_path, len(_hook_state.captured_source_code),
            )
    else:
        if tool_name:
            logger.debug("PostToolUse: skipping non-target tool: %s", tool_name)

    return SyncHookJSONOutput(
        hookSpecificOutput=PostToolUseHookSpecificOutput(
            hookEventName="PostToolUse",
        )
    )
