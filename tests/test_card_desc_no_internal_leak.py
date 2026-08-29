# -*- coding: utf-8 -*-
"""
tests/test_card_desc_no_internal_leak.py — 메인페이지 계산기 카드 description 내부정보 노출 회귀 테스트

배경: docs/registry/*.yaml의 card_desc가 메인페이지(modules/site_generator.generate_index)
카드 설명문구로 그대로 렌더링된다(SSOT, 별도 변환 없음). App Factory 자동생성 항목(labor_af.yaml
등 *_af.yaml)에서 calculator input/output schema 필드명(예: years_of_service, used_days)이나
개발용 계산식이 card_desc에 그대로 들어간 사고가 있었다(2026-08 발견, 수정됨).

검증 항목:
1. card_desc가 자신의 input_labels/output_labels/field_labels 내부 필드명을 그대로 포함하지 않음
2. card_desc에 snake_case_identifier( 형태(schema 표현) 또는 개발용 schema 키워드가 없음
3. card_desc가 "…"/"..."로 끝나며 잘려있지 않음(문장 완성도)
4. card_desc가 비어있지 않음
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.registry_loader import load_registry_v3  # noqa: E402

# 개발용 schema 표현에서 흔히 쓰이는 키워드(§9 지시서 기준 + 실제 registry 필드 패턴 조사).
_SCHEMA_KEYWORDS = [
    "input:", "output:", "params", "schema", "field_name",
    "type:", "required:", "enum:", "calculator_id",
]

# snake_case_identifier( 형태 — 실제로 발생했던 "years_of_service(근속연수, 양의 정수)" 패턴.
_SNAKE_CASE_CALL_RE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\s*\(")

# JSON/dict 리터럴 형태(예: {"years_of_service": ...})
_JSON_LITERAL_RE = re.compile(r'[{"].*:.*[}"]')


def _public_entries():
    """메인페이지에 실제 노출되는(status != HOLD) registry v3 엔트리."""
    v3 = load_registry_v3(force=True)
    return {slug: e for slug, e in v3.items() if e.get("status") != "HOLD"}


def test_card_desc_present_for_every_public_calculator():
    entries = _public_entries()
    assert entries, "registry v3에서 공개 계산기를 하나도 찾지 못함 — 로더 경로 확인 필요"
    for slug, entry in entries.items():
        card_desc = (entry.get("card_desc") or "").strip()
        assert card_desc, f"{slug}: card_desc가 비어있음"


def test_card_desc_not_truncated():
    entries = _public_entries()
    for slug, entry in entries.items():
        card_desc = entry.get("card_desc") or ""
        assert not card_desc.rstrip().endswith(("…", "...")), (
            f"{slug}: card_desc가 말줄임표로 잘려 미완성 문장임 — {card_desc!r}"
        )


def test_card_desc_no_schema_keywords():
    entries = _public_entries()
    for slug, entry in entries.items():
        card_desc = entry.get("card_desc") or ""
        for kw in _SCHEMA_KEYWORDS:
            assert kw not in card_desc, (
                f"{slug}: card_desc에 개발용 schema 키워드 '{kw}' 노출 — {card_desc!r}"
            )
        assert not _SNAKE_CASE_CALL_RE.search(card_desc), (
            f"{slug}: card_desc에 snake_case 내부 식별자 호출 패턴 노출 — {card_desc!r}"
        )
        assert not _JSON_LITERAL_RE.search(card_desc), (
            f"{slug}: card_desc에 JSON/dict 리터럴 형태 노출 — {card_desc!r}"
        )


def test_card_desc_no_own_internal_field_names():
    """각 카드의 card_desc가 자기 자신의 input_labels/output_labels/field_labels 키(내부 필드명)를
    그대로 포함하지 않는지 확인. 실제 필드명은 계산기마다 달라 registry에서 직접 조사한다."""
    entries = _public_entries()
    for slug, entry in entries.items():
        card_desc = entry.get("card_desc") or ""
        internal_names = set(entry.get("field_labels") or {}) | set(
            entry.get("input_labels") or []
        ) | set(entry.get("output_labels") or [])
        for name in internal_names:
            # 2글자 이하 필드명은 오탐 위험이 커서 제외(실제 내부명은 전부 snake_case 3글자 이상).
            if len(name) <= 2:
                continue
            assert name not in card_desc, (
                f"{slug}: card_desc에 내부 필드명 '{name}' 노출 — {card_desc!r}"
            )
