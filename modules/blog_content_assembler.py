# -*- coding: utf-8 -*-
"""
modules/blog_content_assembler.py — Golden10 + DB → 공통 Content Result 조립

STEP 1 설계 확정 사항: content/blog/writer.py, content/calculator/writer.py,
modules/publisher.py, modules/blog_scheduler_adapter.py는 이 모듈에서 전혀
수정하지 않는다. 여기서는 이미 존재하는 두 소스(GOLDEN_10 계약 + calculators DB row)를
읽기만 해서 Static Publisher가 쓸 하나의 dict로 합칠 뿐이다.

authoritative source는 GOLDEN_10 + DB이며, 이 모듈이 만드는 결과물(및 JSON 스냅샷)은
그 둘의 파생물일 뿐 별도의 진실 소스가 아니다.
"""
from __future__ import annotations

from content.blog import GOLDEN_10, get_golden10


class ContentAssemblyError(Exception):
    """Golden10 계약과 DB 데이터가 불일치하거나 필수 데이터가 없을 때 발생.

    불일치를 조용히 보정하지 않고 그대로 오류로 드러낸다.
    """


def _first_nonempty(*values: str) -> str:
    for v in values:
        if v:
            return v
    return ""


def assemble_content_result(calc: dict, cfg: dict) -> dict:
    """DB calculators row(dict) + GOLDEN_10 계약 → 공통 Content Result.

    calc: modules.blog_scheduler_adapter._load_calculator()가 반환하는 것과 동일한
          형태의 calculators 테이블 row dict (최소 'slug', 'article_content' 필요).
    cfg:  SITE_URL 조회용. 없으면 https://calcmate.kr 기본값 사용.

    반환 필드: title, slug, description, date, category, content, image,
              canonical, intent — STEP 1에서 확정한 최소 스키마 그대로.
    """
    slug = calc.get("slug", "")
    gc = get_golden10(slug)
    if gc is None:
        raise ContentAssemblyError(f"Golden10 계약에 없는 slug: {slug!r}")

    content = calc.get("article_content") or ""
    if not content:
        raise ContentAssemblyError(f"article_content가 비어있음: {slug!r}")

    title = _first_nonempty(gc.title, calc.get("seo_title") or "")
    description = _first_nonempty(
        gc.description,
        calc.get("seo_description") or "",
        calc.get("seo_desc") or "",
    )
    date = _first_nonempty(calc.get("generated_at") or "", calc.get("created_at") or "")
    category = calc.get("category") or ""

    site_url = str(cfg.get("SITE_URL", "https://calcmate.kr")).rstrip("/")
    canonical = f"{site_url}/blog/{slug}/"

    return {
        "title": title,
        "slug": slug,
        "description": description,
        "date": date,
        "category": category,
        "content": content,
        "image": None,
        "canonical": canonical,
        "intent": gc.intent,
    }


def assemble_all_golden10(cfg: dict, load_calculator_fn=None) -> list:
    """Golden10 10건 전체에 대해 Content Result를 조립해 리스트로 반환.

    load_calculator_fn(cfg, slug) -> dict|None 을 주입할 수 있다(테스트 격리용).
    기본값은 modules.blog_scheduler_adapter._load_calculator — 기존 DB 조회 로직을
    그대로 재사용하며, 이 함수는 그 로직을 복제하지 않는다.
    """
    if load_calculator_fn is None:
        from modules.blog_scheduler_adapter import _load_calculator as load_calculator_fn

    results = []
    for gc in GOLDEN_10:
        calc = load_calculator_fn(cfg, gc.slug)
        if calc is None:
            raise ContentAssemblyError(f"DB에 없는 Golden10 slug: {gc.slug!r}")
        if calc.get("slug") != gc.slug:
            raise ContentAssemblyError(
                f"DB 조회 결과 slug 불일치: 요청={gc.slug!r} 실제={calc.get('slug')!r}"
            )
        results.append(assemble_content_result(calc, cfg))
    return results
