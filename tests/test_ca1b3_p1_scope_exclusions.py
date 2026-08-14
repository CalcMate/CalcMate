# -*- coding: utf-8 -*-
"""tests/test_ca1b3_p1_scope_exclusions.py — CA-1B-3-B P1: Registry→legal_master→scope_exclusions

검증 항목 (파일 쓰기 없음 — prefill은 읽기 전용, 실제 docs/에 아무것도 쓰지 않음):
  1.  legal_refs → forbidden_articles 매핑 PASS
  2.  legal_refs → forbidden_phrases 매핑 PASS
  3.  articles + phrases 동시 매핑 PASS
  4.  중복 제거 + 문서 순서 유지 PASS
  5.  legal_refs 없음 → []
  6.  forbidden_articles/phrases 없음 → []
  7.  존재하지 않는 legal_ref → 추측 없이 안전 처리
  8.  실제 8개 계산기 실데이터 검증 (severance-pay / unemployment-benefit 등)
  9.  기존 input/output prefill 회귀 (scope_exclusions 추가 후에도 동일)
 10.  found=False → scope_exclusions == []
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import pytest

from modules.app_factory import prefill_contract_from_registry

_EIGHT_SLUGS = [
    "weekly-holiday-allowance",
    "severance-pay",
    "annual-leave-allowance",
    "연말정산_환급액_계산기",
    "freelancer-tax-3p3",
    "unemployment-benefit",
    "육아휴직_급여_계산기",
    "four-insurances",
]

# ── 테스트용 legal_master (주입형 — 실제 YAML 미사용) ────────────────────────
_FAKE_LM = {
    "act_a": {"forbidden_articles": ["근로기준법 제34조"], "forbidden_phrases": []},
    "act_b": {"forbidden_articles": [], "forbidden_phrases": ["받을 수 있습니다", "수급 대상입니다"]},
    "act_c": {
        "forbidden_articles": ["소득세법 제55조", "소득세법 제63조"],
        "forbidden_phrases": ["원천징수로 납세 완료"],
    },
    "act_d": {"forbidden_articles": [], "forbidden_phrases": []},
}


def _mk_reg(legal_refs):
    return {"calc": {"slug": "calc", "name": "C", "category": "c",
                    "input_labels": ["a"], "output_labels": ["b"],
                    "legal_refs": legal_refs}}


# ── 1. legal_refs → forbidden_articles ──────────────────────────────────────
def test_legal_refs_to_forbidden_articles():
    pf = prefill_contract_from_registry("calc", registry=_mk_reg(["act_a"]), legal_master=_FAKE_LM)
    assert pf["found"] is True
    assert pf["scope_exclusions"] == ["근로기준법 제34조"]


# ── 2. legal_refs → forbidden_phrases ───────────────────────────────────────
def test_legal_refs_to_forbidden_phrases():
    pf = prefill_contract_from_registry("calc", registry=_mk_reg(["act_b"]), legal_master=_FAKE_LM)
    assert pf["scope_exclusions"] == ["받을 수 있습니다", "수급 대상입니다"]


# ── 3. articles + phrases 동시 매핑 ─────────────────────────────────────────
def test_articles_and_phrases_together():
    pf = prefill_contract_from_registry("calc", registry=_mk_reg(["act_c"]), legal_master=_FAKE_LM)
    # forbidden_articles 먼저, forbidden_phrases 나중 (문서 필드 순서)
    assert pf["scope_exclusions"] == ["소득세법 제55조", "소득세법 제63조", "원천징수로 납세 완료"]


# ── 4. 중복 제거 + deterministic order ──────────────────────────────────────
def test_dedup_and_order():
    reg = {"calc": {"slug": "calc", "name": "C", "category": "c",
                    "input_labels": [], "output_labels": [],
                    "legal_refs": ["act_c", "act_c", "act_a", "act_c"]}}
    pf = prefill_contract_from_registry("calc", registry=reg, legal_master=_FAKE_LM)
    # act_c(FA 2 + FP 1) → act_a(FA 1) 순, 중복 없이
    assert pf["scope_exclusions"] == [
        "소득세법 제55조", "소득세법 제63조", "원천징수로 납세 완료", "근로기준법 제34조"]


# ── 5. legal_refs 없음 → [] ─────────────────────────────────────────────────
def test_no_legal_refs():
    reg = {"calc": {"slug": "calc", "name": "C", "category": "c",
                    "input_labels": ["a"], "output_labels": ["b"]}}
    pf = prefill_contract_from_registry("calc", registry=reg, legal_master=_FAKE_LM)
    assert pf["scope_exclusions"] == []


# ── 6. forbidden_articles/phrases 없음 → [] ─────────────────────────────────
def test_no_forbidden_fields():
    pf = prefill_contract_from_registry("calc", registry=_mk_reg(["act_d"]), legal_master=_FAKE_LM)
    assert pf["scope_exclusions"] == []


# ── 7. 존재하지 않는 legal_ref → 안전 처리 (추측 없음) ─────────────────────────
def test_unknown_legal_ref_ignored():
    pf = prefill_contract_from_registry("calc", registry=_mk_reg(["no_such_entity"]), legal_master=_FAKE_LM)
    assert pf["found"] is True
    assert pf["scope_exclusions"] == []  # 임의 추측 금지


# ── 8. 실제 8개 계산기 실데이터 검증 ─────────────────────────────────────────
def test_real_calculators_scope_exclusions():
    """legal_master 실제 YAML 기준 예상값과 일치해야 한다 (조사 결과 기반)."""
    expected = {
        "severance-pay": ["근로기준법 제34조"],
        "unemployment-benefit": ["받을 수 있습니다", "받게 됩니다", "수급 대상입니다"],
        "연말정산_환급액_계산기": ["소득세법 제55조", "소득세법 제63조"],
        "freelancer-tax-3p3": ["원천징수로 납세 완료", "종합소득세 신고 불필요"],
        "육아휴직_급여_계산기": ["고용보험법 제40조", "근로기준법 제74조"],
        "weekly-holiday-allowance": [],
        "annual-leave-allowance": [],
        "four-insurances": [],
    }
    for slug, want in expected.items():
        pf = prefill_contract_from_registry(slug)
        assert pf["found"] is True, slug
        assert pf["scope_exclusions"] == want, f"{slug}: {pf['scope_exclusions']} != {want}"


# ── 9. 기존 input/output prefill 회귀 ───────────────────────────────────────
def test_existing_prefill_unchanged_with_scope_exclusions():
    """scope_exclusions 추가 후에도 input/output/name/category 매핑은 그대로."""
    from modules.registry_loader import load_registry_v3

    reg = load_registry_v3(force=True)
    for slug in _EIGHT_SLUGS:
        entry = reg[slug]
        pf = prefill_contract_from_registry(slug)
        assert pf["found"] is True, slug
        assert pf["input_fields"] == list(entry.get("input_labels") or []), slug
        assert pf["output_fields"] == list(entry.get("output_labels") or []), slug
        assert pf["name"] == entry.get("name"), slug
        assert pf["category"] == entry.get("category"), slug
        # scope_exclusions는 리스트여야 하며 (빈 리스트 가능) input/output과 무관
        assert isinstance(pf["scope_exclusions"], list), slug


# ── 10. found=False → scope_exclusions == [] ────────────────────────────────
def test_missing_slug_scope_exclusions_empty():
    pf = prefill_contract_from_registry("no-such-calculator-xyz")
    assert pf["found"] is False
    assert pf["scope_exclusions"] == []
    assert pf["message"]
