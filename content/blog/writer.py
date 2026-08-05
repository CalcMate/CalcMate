# -*- coding: utf-8 -*-
"""
content/blog/writer.py — 블로그 콘텐츠 엔진 작성기 (stub, 미구현)

현재 파이프라인은 content.calculator 엔진만 사용한다.
이 모듈은 향후 블로그 전용 본문 생성 로직을 위한 자리 표시자.
"""


def generate_blog_article(cfg: dict, post: dict, intent: str = None) -> str:
    raise NotImplementedError("blog writer engine not yet implemented")


def auto_generate_blog_all(cfg: dict, post: dict, save: bool = True) -> dict:
    raise NotImplementedError("blog writer engine not yet implemented")
