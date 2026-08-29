# -*- coding: utf-8 -*-
"""
content/blog/template.py — 블로그 콘텐츠 HTML 템플릿 어댑터

Golden 10 재현성 테스트를 위한 최소 HTML 조립 로직.
"""
import json


def build_blog_html(body: str, faq: list = None, calc_slug: str = "", calc_name: str = "") -> str:
    """블로그 콘텐츠 HTML 조립 — body HTML + 인라인 FAQ + 계산기 CTA.

    기존 Golden 10 사이트 출력과 동일한 구조를 유지한다.
    """
    parts = [body]

    # 인라인 FAQ (<dl> 형식)
    if faq:
        faq_html = '<h2>FAQ</h2>\n<dl class="faq-list">\n'
        for item in faq:
            q = item.get("question", "")
            a = item.get("answer", "")
            if q and a:
                faq_html += f'  <dt>{q}</dt>\n  <dd>{a}</dd>\n'
        faq_html += '</dl>\n'
        # FAQ가 이미 body에 없을 때만 추가
        if '<dl class="faq-list">' not in body and '<dl>' not in body:
            parts.append(faq_html)

    return "\n".join(parts)


def build_blog_jsonld(post: dict, faq: list = None) -> dict:
    """블로그 JSON-LD 메타데이터 — FAQ Schema."""
    if not faq:
        return {}

    items = []
    for item in faq:
        q = item.get("question", "")
        a = item.get("answer", "")
        if q and a:
            items.append({
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": a,
                }
            })

    if not items:
        return {}

    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": items,
    }
