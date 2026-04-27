from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest
from fastapi import HTTPException

from backend.content_clarifier import ContentClarifyError, clarify_content
from backend.models import ContentClarifyData, ContentClarifyRequest
from backend.routes import clarify_content_route


class _FakeAsyncClient:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, *_args, **_kwargs):
        return self.response


def _clarify_payload() -> dict[str, object]:
    return {
        "topic_interpretation": "Explain the topic as a math animation.",
        "core_question": "What is the core idea?",
        "prerequisite_concepts": ["definition"],
        "explanation_path": ["intuition", "example"],
        "scope_boundaries": [],
        "optional_branches": [],
        "animation_focus": ["visual contrast"],
        "ambiguity_notes": [],
        "clarified_brief_cn": "Clarified brief.",
        "recommended_request_cn": "Create an animation explaining the topic clearly.",
    }


@pytest.mark.asyncio
async def test_clarify_content_route_returns_structured_result():
    async def _fake_clarify(_user_text: str) -> ContentClarifyData:
        return ContentClarifyData(
            topic_interpretation="默认按向量分析中的高斯散度定理理解。",
            core_question="为什么体内源汇总量可以转成边界总通量？",
            prerequisite_concepts=["向量场", "通量"],
            explanation_path=["直觉现象", "公式表达", "简单例子"],
            scope_boundaries=["默认不展开严格证明"],
            optional_branches=["物理中的高斯定律"],
            animation_focus=["箭头流场", "封闭曲面"],
            ambiguity_notes=["可能与其他高斯相关结论混淆"],
            clarified_brief_cn="默认按散度定理来理解，重点讲通量与散度的关系。",
            recommended_request_cn=(
                "请用教学动画讲解向量分析中的高斯散度定理，重点说明体内散度总量"
                "与边界曲面总通量之间的对应关系。"
            ),
        )

    with patch("backend.routes.clarify_content", _fake_clarify):
        response = await clarify_content_route(ContentClarifyRequest(user_text="高斯定理"))

    assert response.original_user_text == "高斯定理"
    assert response.clarification.topic_interpretation.startswith("默认按")
    assert "通量" in response.clarification.recommended_request_cn


@pytest.mark.asyncio
async def test_clarify_content_route_maps_clarifier_errors_to_503():
    async def _fake_clarify(_user_text: str) -> ContentClarifyData:
        raise ContentClarifyError("clarifier unavailable")

    with patch("backend.routes.clarify_content", _fake_clarify):
        with pytest.raises(HTTPException) as exc_info:
            await clarify_content_route(ContentClarifyRequest(user_text="高斯定理"))

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "clarifier unavailable"


@pytest.mark.asyncio
async def test_clarify_content_accepts_openai_style_choices(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    response = httpx.Response(
        200,
        json={
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(_clarify_payload()),
                    }
                }
            ]
        },
    )

    with patch(
        "backend.content_clarifier.httpx.AsyncClient",
        return_value=_FakeAsyncClient(response),
    ):
        result = await clarify_content("topic")

    assert result.core_question == "What is the core idea?"


@pytest.mark.asyncio
async def test_clarify_content_accepts_string_content(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    response = httpx.Response(
        200,
        json={"content": json.dumps(_clarify_payload())},
    )

    with patch(
        "backend.content_clarifier.httpx.AsyncClient",
        return_value=_FakeAsyncClient(response),
    ):
        result = await clarify_content("topic")

    assert result.recommended_request_cn == "Create an animation explaining the topic clearly."
