"""Lightweight Anthropic-compatible content clarification service."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .models import ContentClarifyData


DEFAULT_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").strip()
DEFAULT_MODEL = os.environ.get(
    "ANTHROPIC_CLARIFIER_MODEL",
    os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
)
DEFAULT_MAX_TOKENS = 1400


def _resolve_messages_url(base_url: str) -> str:
    """Resolve an Anthropic-compatible /v1/messages endpoint from a base URL."""
    normalized = base_url.rstrip("/")
    if normalized.endswith("/messages"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/messages"
    return f"{normalized}/v1/messages"


SYSTEM_PROMPT = """
你是一个“数学动画内容澄清助手”。
你的任务不是生成代码，也不是安排时长、画质、配音或制作参数。
你只负责把用户输入的主题说明得更清楚，让它更适合后续生成教学动画。

请根据用户输入，输出一个 JSON 对象，字段必须严格包含：
- topic_interpretation: 默认如何理解这个主题
- core_question: 这个主题想回答的核心问题
- prerequisite_concepts: 讲清这个主题前，默认需要铺垫的关键前置概念数组
- explanation_path: 推荐的讲解主线数组，按顺序排列
- scope_boundaries: 本次默认不展开或不深入的边界数组
- optional_branches: 用户后续可以改成的分支方向数组
- animation_focus: 最适合动画表达的重点数组
- ambiguity_notes: 需要提醒用户确认的歧义或可能混淆点数组
- clarified_brief_cn: 给用户看的中文内容理解确认摘要，1 段即可
- recommended_request_cn: 推荐提交给动画生成系统的中文内容说明，要求比原始输入更清楚、更具体，但不要加入时长、画质、配音、BGM 等执行参数

要求：
- 全部使用简体中文
- 不要输出 markdown
- 不要输出 JSON 以外的内容
- 如果用户输入非常短，也要做出一个合理的默认理解
- 如果存在歧义，要在 ambiguity_notes 里明确指出，但仍然给出 best-guess interpretation
- recommended_request_cn 要像用户最终提交的一段自然语言任务说明，而不是字段列表
""".strip()


class ContentClarifyError(RuntimeError):
    """Raised when content clarification cannot complete successfully."""


def _extract_text_content(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    if not isinstance(content, list):
        raise ContentClarifyError("Clarifier response missing content blocks")

    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text)

    if not parts:
        raise ContentClarifyError("Clarifier response did not contain text output")
    return "\n".join(parts).strip()


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = [line for line in stripped.splitlines() if not line.strip().startswith("```")]
        stripped = "\n".join(lines).strip()

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ContentClarifyError("Clarifier response did not contain a JSON object")

    try:
        return json.loads(stripped[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ContentClarifyError(f"Clarifier returned invalid JSON: {exc}") from exc


async def clarify_content(user_text: str) -> ContentClarifyData:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise ContentClarifyError("ANTHROPIC_API_KEY is not set")

    api_url = _resolve_messages_url(DEFAULT_BASE_URL)
    payload = {
        "model": DEFAULT_MODEL,
        "max_tokens": DEFAULT_MAX_TOKENS,
        "temperature": 0.2,
        "system": SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": f"请澄清这个动画主题输入：{user_text.strip()}",
            }
        ],
    }

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(api_url, headers=headers, json=payload)

    if response.status_code >= 400:
        raise ContentClarifyError(
            f"Clarifier API error {response.status_code}: {response.text.strip()}"
        )

    response_json = response.json()
    raw_text = _extract_text_content(response_json)
    raw_data = _extract_json_object(raw_text)
    return ContentClarifyData.model_validate(raw_data)
