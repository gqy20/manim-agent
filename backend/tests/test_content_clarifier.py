from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from backend.content_clarifier import ContentClarifyError
from backend.models import ContentClarifyData, ContentClarifyRequest
from backend.routes import clarify_content_route


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
