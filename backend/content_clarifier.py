"""Lightweight Anthropic-compatible content clarification service."""
# ruff: noqa: E501

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import httpx

from .log_config import log_event
from .models import ContentClarifyData

DEFAULT_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").strip()
DEFAULT_MODEL = os.environ.get(
    "ANTHROPIC_CLARIFIER_MODEL",
    os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
)
DEFAULT_MAX_TOKENS = 1400
DEFAULT_TIMEOUT_SECONDS = float(os.environ.get("ANTHROPIC_CLARIFIER_TIMEOUT_SECONDS", "60"))
logger = logging.getLogger(__name__)


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


SYSTEM_PROMPT = """
你是一个“数学动画内容澄清助手”。你的任务不是生成代码，也不是安排时长、
画质、配音或制作参数。你只负责把用户输入的主题说明得更清楚，让它更适合后续
生成教学动画。

请根据用户输入，只输出一个 JSON 对象，不要输出 markdown 或 JSON 以外的内容。
字段必须严格包含：
- topic_interpretation: 默认如何理解这个主题
- core_question: 这个主题想回答的核心问题
- prerequisite_concepts: 讲清主题前需要铺垫的关键前置概念数组
- explanation_path: 推荐的讲解主线数组，按顺序排列
- scope_boundaries: 本次默认不展开或不深入的边界数组
- optional_branches: 用户后续可以改成的分支方向数组
- animation_focus: 最适合动画表达的重点数组
- ambiguity_notes: 需要提醒用户确认的歧义或可能混淆点数组
- clarified_brief_cn: 给用户看的中文内容理解确认摘要，1 段即可
- recommended_request_cn: 推荐提交给动画生成系统的中文内容说明

要求：
- 全部使用简体中文
- 如果用户输入很短，也要给出合理的默认理解
- 如果存在歧义，在 ambiguity_notes 里明确指出，但仍然给出 best-guess interpretation
- recommended_request_cn 要像用户最终提交的一段自然语言任务说明
- 不要加入时长、画质、配音、BGM 等执行参数
""".strip()


class ContentClarifyError(RuntimeError):
    """Raised when content clarification cannot complete successfully."""


def _extract_text_content(payload: dict[str, Any]) -> str:
    direct_text = payload.get("output_text") or payload.get("text")
    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text.strip()

    choices = payload.get("choices")
    if isinstance(choices, list):
        parts: list[str] = []
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message") or choice.get("delta")
            if isinstance(message, dict):
                content = message.get("content")
                extracted = _extract_text_from_content_value(content)
                if extracted:
                    parts.append(extracted)
            extracted = _extract_text_from_content_value(choice.get("text"))
            if extracted:
                parts.append(extracted)
        if parts:
            return "\n".join(parts).strip()

    content = payload.get("content")
    extracted = _extract_text_from_content_value(content)
    if extracted:
        return extracted

    raise ContentClarifyError("Clarifier response missing text content")


def _extract_text_from_content_value(content: Any) -> str | None:
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, dict):
        text = content.get("text") or content.get("content")
        if isinstance(text, str) and text.strip():
            return text.strip()
        if _looks_like_clarify_payload(content):
            return json.dumps(content, ensure_ascii=False)
        return None
    if not isinstance(content, list):
        return None

    parts: list[str] = []
    for block in content:
        if isinstance(block, str) and block.strip():
            parts.append(block)
        elif isinstance(block, dict):
            text = block.get("text") or block.get("content")
            if isinstance(text, str) and text.strip():
                parts.append(text)
            elif _looks_like_clarify_payload(block):
                parts.append(json.dumps(block, ensure_ascii=False))

    if not parts:
        return None
    return "\n".join(parts).strip()


def _looks_like_clarify_payload(value: dict[str, Any]) -> bool:
    return "core_question" in value and "recommended_request_cn" in value


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
    started_at = time.perf_counter()
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

    log_event(
        logger,
        logging.INFO,
        "clarifier_request_started",
        model=DEFAULT_MODEL,
        api_base=DEFAULT_BASE_URL,
        text_len=len(user_text.strip()),
    )

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS, trust_env=False) as client:
            response = await client.post(api_url, headers=headers, json=payload)
    except httpx.TimeoutException as exc:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        log_event(
            logger,
            logging.ERROR,
            "clarifier_timeout",
            model=DEFAULT_MODEL,
            duration_ms=duration_ms,
            timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
            error_type=type(exc).__name__,
        )
        raise ContentClarifyError("Content clarification timed out. Please retry.") from exc
    except httpx.RequestError as exc:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        log_event(
            logger,
            logging.ERROR,
            "clarifier_request_failed",
            model=DEFAULT_MODEL,
            duration_ms=duration_ms,
            error_type=type(exc).__name__,
        )
        raise ContentClarifyError(
            "Content clarification service is temporarily unavailable."
        ) from exc

    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    log_event(
        logger,
        logging.INFO,
        "clarifier_response_received",
        model=DEFAULT_MODEL,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )

    if response.status_code >= 400:
        log_event(
            logger,
            logging.ERROR,
            "clarifier_http_error",
            model=DEFAULT_MODEL,
            status_code=response.status_code,
            duration_ms=duration_ms,
            error_type="http_error",
        )
        raise ContentClarifyError(
            f"Clarifier API error {response.status_code}: {response.text.strip()}"
        )

    try:
        response_json = response.json()
        raw_text = _extract_text_content(response_json)
        raw_data = _extract_json_object(raw_text)
        result = ContentClarifyData.model_validate(raw_data)
    except Exception as exc:
        response_preview = response.text[:800].replace("\n", "\\n")
        log_event(
            logger,
            logging.ERROR,
            "clarifier_parse_failed",
            model=DEFAULT_MODEL,
            duration_ms=duration_ms,
            error_type=type(exc).__name__,
            response_preview=response_preview,
        )
        if isinstance(exc, ContentClarifyError):
            raise
        raise ContentClarifyError(f"Clarifier response could not be parsed: {exc}") from exc

    log_event(
        logger,
        logging.INFO,
        "clarifier_completed",
        model=DEFAULT_MODEL,
        duration_ms=duration_ms,
        core_question=result.core_question,
    )
    return result
