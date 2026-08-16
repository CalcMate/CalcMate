# -*- coding: utf-8 -*-
"""
modules/cta_builder.py — CTA 블록 + 내부링크 블록 생성

Phase 5-C 게시 직전 후처리 단계에서 호출.
AI 생성 단계에서 삽입하지 않고 publish 직전에 시스템이 삽입 (_NO_LINK_RULE 유지).
"""
from __future__ import annotations
import pathlib
import re

_MASTER_PATH = pathlib.Path(__file__).resolve().parent.parent / "docs" / "legal_basis.master.yaml"
_DEFAULT_SITE_URL = "https://calcmate.kr"


def _load_master() -> dict:
    import yaml
    return yaml.safe_load(_MASTER_PATH.read_text(encoding="utf-8")) or {}


def build_cta_block(slug: str, calc_name: str, site_url: str = _DEFAULT_SITE_URL) -> str:
    """
    <h2>계산기 사용하기</h2> 섹션 HTML 생성.
    publish_quality.py G6 gate 기준: <h2>계산기 사용하기</h2> 포함 필수.
    """
    url = f"{site_url}/{slug}/"
    return (
        "\n<h2>계산기 사용하기</h2>\n"
        f"<p>{calc_name}로 정확한 금액을 직접 계산해 보세요.</p>\n"
        f'<p><a href="{url}" target="_blank" rel="noopener">{calc_name} 바로가기</a></p>\n'
    )


def build_internal_links_block(
    slug: str,
    site_url: str = _DEFAULT_SITE_URL,
    max_links: int = 3,
) -> str:
    """
    <div class="internal-links"> 블록 생성.
    legal_basis.master.yaml의 related_slugs를 사용.
    """
    master = _load_master()
    entry = master.get(slug, {})
    related = entry.get("related_slugs", [])[:max_links]

    if not related:
        return ""

    link_items = []
    for rel_slug in related:
        rel_entry = master.get(rel_slug, {})
        rel_name = rel_entry.get("name", rel_slug)
        rel_url = f"{site_url}/{rel_slug}/"
        link_items.append(
            f'<li><a href="{rel_url}" target="_blank" rel="noopener">{rel_name}</a></li>'
        )

    links_html = "\n".join(link_items)
    return (
        '\n<div class="internal-links">\n'
        "<p>관련 계산기</p>\n"
        f"<ul>\n{links_html}\n</ul>\n"
        "</div>\n"
    )


def inject_cta_and_links(
    body_html: str,
    slug: str,
    calc_name: str,
    site_url: str = _DEFAULT_SITE_URL,
) -> tuple[str, dict]:
    """
    본문 HTML에 CTA 블록 + 내부링크 블록을 append.
    이미 CTA가 있으면 삽입 생략 (중복 방지).

    Returns:
        (modified_html, report_dict)
        report_dict: {cta_inserted: bool, links_inserted: bool, internal_links_count: int}
    """
    report = {"cta_inserted": False, "links_inserted": False, "internal_links_count": 0}

    # CTA 중복 방지
    _CTA_MARKER = "<h2>계산기 사용하기</h2>"
    if _CTA_MARKER not in body_html:
        cta_block = build_cta_block(slug, calc_name, site_url)
        body_html = body_html.rstrip() + cta_block
        report["cta_inserted"] = True

    # 내부링크 중복 방지
    _LINKS_MARKER = 'class="internal-links"'
    if _LINKS_MARKER not in body_html:
        links_block = build_internal_links_block(slug, site_url)
        if links_block:
            body_html = body_html.rstrip() + links_block
            report["links_inserted"] = True
            report["internal_links_count"] = len(
                re.findall(r'<li><a ', links_block)
            )

    return body_html, report


def validate_calc_url_structure(slug: str, site_url: str = _DEFAULT_SITE_URL) -> dict:
    """
    계산기 URL 구조 검증 (HTTP 요청 없이 slug 기반).
    known=True 이면 master YAML에 등록된 slug.
    """
    master = _load_master()
    known = slug in master
    url = f"{site_url}/{slug}/"
    return {"url": url, "slug": slug, "known": known, "valid": known}
