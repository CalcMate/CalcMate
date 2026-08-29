# -*- coding: utf-8 -*-
"""
content/blog/prompt.py — 블로그 콘텐츠 프롬프트 어댑터

content.calculator.prompt 의 intent별 템플릿을 블로그 라인에서 재사용.
별도 V2 프롬프트 엔진을 새로 만들지 않고, 기존 intent 분기를 그대로 활용.
"""
from content.calculator.prompt import get_article_prompt, get_seo_prompt, get_faq_prompt, QUALITY


def get_blog_article_prompt(post: dict, intent: str = None) -> tuple:
    """블로그 콘텐츠 생성 프롬프트 — content.calculator.prompt 재사용.

    Args:
        post: 계산기 dict (name, category, seo_desc, formula, input_schema, output_schema 등)
        intent: eligibility / howto / documents / calculator 중 하나

    Returns:
        (system, user) tuple
    """
    seo = {}
    if post.get("seo_title"):
        seo["seo_title"] = post["seo_title"]
    if post.get("seo_description"):
        seo["seo_description"] = post["seo_description"]

    faq = post.get("faq") or []
    example_context = post.get("example_context")

    return get_article_prompt(post, seo=seo, faq=faq, example_context=example_context, intent=intent)


def get_blog_seo_prompt(post: dict) -> tuple:
    """블로그 SEO 프롬프트 — content.calculator.prompt 재사용."""
    return get_seo_prompt(post)
