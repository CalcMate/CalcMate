# -*- coding: utf-8 -*-
"""
modules/law_ssot.py — LAW_SSOT 로더

legal_basis.master.yaml의 content_ssot 섹션에서 slug별 법정수치 SSOT를 로드.
G-LEGAL-CURRENT Gate 및 생성 프롬프트 주입에서 사용한다.
"""
from __future__ import annotations
import hashlib
import json
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


def get_positive_check_items(slug: str, intent: str) -> list[dict]:
    """
    content_ssot.items 중 requires_in_content_for_intents에 intent가 포함된 항목 반환.
    각 항목: {value, item, effective_year, legal_basis}
    """
    ssot = get_slug_ssot(slug)
    result: list[dict] = []
    for item in ssot.get("items", []):
        required_for = item.get("requires_in_content_for_intents", [])
        if intent in required_for:
            result.append({
                "value": item.get("value", ""),
                "item": item.get("item", ""),
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

    # 금액 미언급 정책(forbid_amounts)이면 강력한 금지 지시문 추가
    if get_amount_ban_flag(slug):
        lines.append(
            "\n[금액 미언급 필수 지시 — 반드시 준수]\n"
            "- 이 글에는 어떤 금액(만원·원 단위)도 절대 언급하지 않는다.\n"
            "- 계산 예시를 들 때도 통상임금·급여를 숫자로 쓰지 않고 '통상임금'이라고만 표현한다.\n"
            "- '금액은 고용노동부 최신 안내를 참고' 취지로 서술한다."
        )
    return "\n".join(lines)


def get_amount_ban_flag(slug: str) -> bool:
    """
    slug의 content_ssot 항목 중 forbid_amounts: true 가 있는지 여부.
    True면 게시물 본문/FAQ에 금액(만원·원 단위) 자체가 등장해서는 안 된다.
    """
    ssot = get_slug_ssot(slug)
    return any(
        item.get("forbid_amounts")
        for item in ssot.get("items", [])
    )


def get_related_slugs(slug: str) -> list[str]:
    """slug의 related_slugs 반환 (내부링크 자동삽입 용)."""
    return get_slug_entry(slug).get("related_slugs", [])


def get_calc_name(slug: str) -> str:
    """slug의 계산기 이름 반환. 없으면 slug 그대로."""
    return get_slug_entry(slug).get("name", slug)


def content_ssot_hash(slug: str) -> str:
    """STEP 28-52: slug의 content_ssot.items[]를 정규화해 SHA256 hex digest로 반환.
    dict key 순서나 YAML의 formatting/공백/주석 변경에는 영향받지 않고, items의
    실제 값이 바뀔 때만 달라진다(confidence/last_verified 등 메타데이터는
    get_slug_ssot()가 반환하는 content_ssot 블록 중 items만 사용하므로 무관).
    신규 YAML 파서 없이 기존 get_slug_ssot()만 재사용한다."""
    items = get_slug_ssot(slug).get("items", [])
    normalized = json.dumps(items, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
