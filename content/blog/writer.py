# -*- coding: utf-8 -*-
"""
content/blog/writer.py — 블로그 콘텐츠 생성 어댑터

Golden 10 블로그 콘텐츠 재현성을 위한 최소 writer.
content.calculator.writer.generate_article()를 intent와 함께 호출하는 얇은 어댑터.
"""
import json
import re

from content.calculator.writer import generate_article
from content.calculator.prompt import get_article_prompt, QUALITY


def _mock_generate_intent(post: dict, seo: dict, faq: list, intent: str) -> str:
    """Mock: OPENAI_API_KEY 없을 때 intent별 고정 콘텐츠 생성.

    calculator.writer.generate_article()의 mock 경로는 intent를 무시하므로,
    블로그 라인에서는 intent별 prompt 템플릿의 구조를 그대로 따르는
    확정론적 mock을 사용한다.
    """
    name = post.get("name", "")
    example_str = json.dumps(post.get("example_context", {}), ensure_ascii=False)

    faq_html = ""
    if faq:
        faq_items = ""
        for item in faq[:5]:
            q = item.get("question", "")
            a = item.get("answer", "")
            if q and a:
                faq_items += f"<dt>{q}</dt><dd>{a}</dd>"
        if faq_items:
            faq_html = f"<dl>{faq_items}</dl>"

    if intent == "eligibility":
        return (
            f"<p>{name}의 지급 대상과 수급 자격을 확인합니다.</p>"
            f"<h2>지급 대상</h2><p>{name}의 지급 대상은 근로기준법 등 관련 법령에 따라 판정합니다."
            f"근로자가 신청할 수 있는지, 고용주가 지급할 의무가 있는지를 함께 확인해야 합니다.</p>"
            f"<h2>근로시간 조건</h2><p>주 15시간 이상 근무 및 6개월 이상 근속이 기본 조건입니다."
            f"근로시간에 따라 지급액이 달라지므로 정확한 확인이 필요합니다.</p>"
            f"<h2>제외 대상</h2><p>특정 조건을 충족하지 못하면 지급받을 수 없습니다."
            f"사업장 규모, 근무 기간, 고용 형태 등에 따라 달라집니다.</p>"
            f"<h2>계산 방법</h2><p>기본 계산 공식에 따라 산정됩니다.</p>"
            f"<p>검증된 데이터: {example_str}</p>"
            f"<h2>FAQ</h2>{faq_html}"
        )
    elif intent == "howto":
        return (
            f"<p>{name}의 이용 방법과 절차를 안내합니다.</p>"
            f"<h2>이용 절차</h2><p>1단계: 필요한 정보를 확인합니다. "
            f"2단계: 계산기를 이용하여 결과를 확인합니다. "
            f"3단계: 결과를 바탕으로 판단합니다.</p>"
            f"<h2>계산 예시</h2><p>검증된 데이터를 바탕으로 실제 계산합니다.</p>"
            f"<p>검증된 데이터: {example_str}</p>"
            f"<h2>주의사항</h2><p>입력값 오류에 주의하세요. 법령 기준이 변경될 수 있습니다.</p>"
            f"<h2>FAQ</h2>{faq_html}"
        )
    elif intent == "documents":
        return (
            f"<p>{name}과 관련된 필요 서류와 제출 방법을 안내합니다.</p>"
            f"<h2>필수 서류 목록</h2><p>신청 및 처리에 필요한 서류를 확인합니다.</p>"
            f"<h2>서류 발급 방법</h2><p>각 서류의 발급처와 발급 절차를 안내합니다.</p>"
            f"<h2>제출 기한 및 절차</h2><p>서류 제출 방법과 기한을 확인합니다.</p>"
            f"<h2>주의사항</h2><p>서류 미비 시 처리가 지연될 수 있습니다.</p>"
            f"<h2>FAQ</h2>{faq_html}"
        )
    else:  # calculator
        return (
            f"<p>{name}의 계산 원리와 방법을 설명합니다.</p>"
            f"<h2>계산 원리</h2><p>법적 근거와 계산 단계를 설명합니다.</p>"
            f"<h2>지급 조건</h2><p>대상 조건과 제외 조건을 확인합니다.</p>"
            f"<h2>주의사항</h2><p>자주 발생하는 오류와 주의점을 안내합니다.</p>"
            f"<h2>FAQ</h2>{faq_html}"
        )


def generate_blog_article(cfg: dict, post: dict, intent: str = None) -> str:
    """블로그 콘텐츠 생성 — content.calculator.writer 재사용 + intent 전달.

    OPENAI_API_KEY가 있으면 calculator.writer.generate_article()을 경유.
    없으면 intent별 mock을 사용 (재현성 테스트용).

    Args:
        cfg: 설정 dict (OPENAI_API_KEY 등)
        post: 계산기 dict (name, category, seo_desc, formula 등)
        intent: eligibility / howto / documents / calculator 중 하나

    Returns:
        생성된 HTML 문자열
    """
    seo = {}
    if post.get("seo_title"):
        seo["seo_title"] = post["seo_title"]
    if post.get("seo_description"):
        seo["seo_description"] = post["seo_description"]

    faq = post.get("faq") or []
    if isinstance(faq, str):
        try:
            faq = json.loads(faq)
        except Exception:
            faq = []

    example_context = post.get("example_context")

    # OPENAI_API_KEY가 없으면 intent별 mock 사용 (calculator.writer mock은 intent 무시)
    if "OPENAI_API_KEY" not in cfg:
        return _mock_generate_intent(post, seo, faq, intent)

    return generate_article(
        cfg, post,
        seo=seo,
        faq=faq,
        example_context=example_context,
        intent=intent,
    )


def auto_generate_blog_all(cfg: dict, post: dict, save: bool = True,
                           intent: str = None) -> dict:
    """블로그 콘텐츠 자동 생성 — 단일 콘텐츠 생성 + 결과 반환.

    DB 저장은 하지 않는다 (isolated reproduction 테스트용).
    """
    article = generate_blog_article(cfg, post, intent=intent)

    return {
        "slug": post.get("slug", ""),
        "name": post.get("name", ""),
        "intent": intent,
        "article_content": article,
        "len": len(article),
    }
