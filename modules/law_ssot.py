# -*- coding: utf-8 -*-
"""
modules/law_ssot.py — LAW_SSOT 로더

legal_basis.master.yaml의 content_ssot 섹션에서 slug별 법정수치 SSOT를 로드.
G-LEGAL-CURRENT Gate 및 생성 프롬프트 주입에서 사용한다.
"""
from __future__ import annotations
import pathlib
from functools import lru_cache

_MASTER_PATH = pathlib.Path(__file__).resolve().parent.parent / "docs" / "legal_basis.master.yaml"


@lru_cache(maxsize=1)
def _load_master() -> dict:
    import yaml
    raw = _MASTER_PATH.read_text(encoding="utf-8")
    return yaml.safe_load(raw) or {}


def get_slug_entry(slug: str) -> dict:
    """slug의 전체 master 항목 반환. 없으면 {}"""
    return _load_master().get(slug, {})


def get_slug_ssot(slug: str) -> dict:
    """slug의 content_ssot 섹션 반환. 없으면 {}"""
    return get_slug_entry(slug).get("content_ssot", {})


def get_forbidden_in_content(slug: str) -> list[dict]:
    """
    slug에서 콘텐츠 본문에 등장해서는 안 되는 항목 목록 반환.
    각 항목: {value, item, current, effective_year, legal_basis}
    """
    ssot = get_slug_ssot(slug)
    result: list[dict] = []
    for item in ssot.get("items", []):
        for forbidden in item.get("forbidden_in_content", []):
            result.append({
                "value": str(forbidden),
                "item": item.get("item", ""),
                "current": item.get("value", ""),
                "effective_year": item.get("effective_year"),
                "legal_basis": item.get("legal_basis", ""),
            })
    return result


def get_ssot_prompt_block(slug: str) -> str:
    """
    생성 프롬프트에 주입할 SSOT 블록 문자열 반환.
    content_ssot.items의 item/value/legal_basis를 한국어 지시문으로 변환.
    없으면 빈 문자열.
    """
    ssot = get_slug_ssot(slug)
    items = ssot.get("items", [])
    if not items:
        return ""

    year = ssot.get("effective_year", "현행")
    lines = [f"[{year}년 현행 법정수치 — 이 값만 사용, AI 추측 절대 금지]"]
    for it in items:
        line = f"- {it['item']}: {it['value']}"
        if it.get("legal_basis"):
            line += f"  (근거: {it['legal_basis']})"
        lines.append(line)
    return "\n".join(lines)


def get_related_slugs(slug: str) -> list[str]:
    """slug의 related_slugs 반환 (내부링크 자동삽입 용)."""
    return get_slug_entry(slug).get("related_slugs", [])


def get_calc_name(slug: str) -> str:
    """slug의 계산기 이름 반환. 없으면 slug 그대로."""
    return get_slug_entry(slug).get("name", slug)
