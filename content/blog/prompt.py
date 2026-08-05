# -*- coding: utf-8 -*-
"""
content/blog/prompt.py — 블로그 콘텐츠 엔진 프롬프트 (stub, 미구현)

현재 파이프라인은 content.calculator 엔진만 사용한다.
이 모듈은 향후 블로그 전용 프롬프트 로직을 위한 자리 표시자.
"""


def get_blog_article_prompt(post: dict, intent: str = None) -> tuple:
    raise NotImplementedError("blog prompt engine not yet implemented")


def get_blog_seo_prompt(post: dict) -> tuple:
    raise NotImplementedError("blog prompt engine not yet implemented")
