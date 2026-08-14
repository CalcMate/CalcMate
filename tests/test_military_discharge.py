# -*- coding: utf-8 -*-
"""tests/test_military_discharge.py — 군인 전역일 계산기 (Tier2-B) 테스트

검증 범위:
  - 전역일 계산식: 입영일 + N개월 - 1일 (관행 계산식)
  - 5개 군별 TC (TC-1~5) + 월말 (TC-6) + 미래 (TC-7)
  - 윤년 2월29일 입대 (TC-윤년)
  - 말일 클램프 (TC-말일)
  - build_contract Tier2-B 기본 검증
  - HOLD-3 발동 확인 (military_service_act_18/30 confidence=medium)
  - _build_tier2b_app 반환 필드 검증
"""
import sys
from pathlib import Path
from datetime import date

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from dateutil.relativedelta import relativedelta

from modules.app_factory import build_contract, check_hold_rules, _build_tier2b_app

_DUTY_MONTHS = {
    "army": 18,
    "marine": 18,
    "navy": 20,
    "air_force": 21,
    "social_service": 21,
}


def calc_discharge_date(enlistment: date, branch: str) -> date:
    months = _DUTY_MONTHS[branch]
    return enlistment + relativedelta(months=months) - relativedelta(days=1)


# ─── 1. 전역일 계산 정확성 ──────────────────────────────────────────────────────

@pytest.mark.parametrize("enlistment,branch,expected", [
    (date(2025, 1, 15), "army",           date(2026, 7, 14)),   # TC-1: 육군 18개월
    (date(2025, 1, 15), "navy",           date(2026, 9, 14)),   # TC-2: 해군 20개월
    (date(2025, 1, 15), "air_force",      date(2026, 10, 14)),  # TC-3: 공군 21개월
    (date(2025, 1, 15), "marine",         date(2026, 7, 14)),   # TC-4: 해병대 18개월
    (date(2025, 1, 15), "social_service", date(2026, 10, 14)),  # TC-5: 사복요원 21개월
    (date(2025, 1, 31), "navy",           date(2026, 9, 29)),   # TC-6: 월말 입대 (Sep=30일 → clamp)
    (date(2027, 6,  1), "army",           date(2028, 11, 30)),  # TC-7: 미래 입대
    (date(2024, 2, 29), "army",           date(2025, 8, 28)),   # TC-윤년: 2월29일 입대
    (date(2025, 5, 31), "air_force",      date(2027, 2, 27)),   # TC-말일: Feb=28일 clamp
])
def test_calc_discharge_date(enlistment, branch, expected):
    assert calc_discharge_date(enlistment, branch) == expected


# ─── 2. 스코프 제외 항목 확인 ───────────────────────────────────────────────────

def test_scope_exclusions_in_contract():
    contract = build_contract(
        slug="military-discharge-date",
        name="군인 전역일 계산기",
        category="병역/공무",
        tier="Tier2-B",
        input_fields=["enlistment_date", "branch"],
        output_fields=["discharge_date", "remaining_days", "progress_pct"],
        formula=None,
        formula_status="operator_confirmed",
        scope_exclusions=["군기교육 복무 미산입", "복무이탈 미산입", "개인별 복무기간 조정"],
        test_cases=[],
        desc="입영일과 군별을 선택하면 예상 전역일을 계산합니다.",
        legal_refs=["military_service_act_18", "military_service_act_30"],
    )
    excl = contract.get("scope_exclusions", [])
    assert "군기교육 복무 미산입" in excl
    assert "복무이탈 미산입" in excl
    assert "개인별 복무기간 조정" in excl


# ─── 3. Contract 생성 (Tier2-B) ──────────────────────────────────────────────

def test_build_contract_tier2b():
    contract = build_contract(
        slug="military-discharge-date",
        name="군인 전역일 계산기",
        category="병역/공무",
        tier="Tier2-B",
        input_fields=["enlistment_date", "branch"],
        output_fields=["discharge_date", "remaining_days", "progress_pct"],
        formula=None,
        formula_status="operator_confirmed",
        scope_exclusions=[],
        test_cases=[],
        desc="",
        legal_refs=["military_service_act_18", "military_service_act_30"],
    )
    assert contract["tier"] == "Tier2-B"
    assert contract["slug"] == "military-discharge-date"
    assert "enlistment_date" in contract["input_fields"]
    assert "discharge_date" in contract["output_fields"]
    assert contract.get("formula_status") == "operator_confirmed"
    assert "military_service_act_18" in contract.get("legal_refs", [])
    assert "military_service_act_30" in contract.get("legal_refs", [])


# ─── 4. HOLD-3 발동 확인 ─────────────────────────────────────────────────────

def test_hold3_fires_for_medium_confidence():
    """military_service_act_18/30 (confidence=medium) 참조 시 HOLD-3가 발동한다."""
    contract = build_contract(
        slug="military-discharge-date",
        name="군인 전역일 계산기",
        category="병역/공무",
        tier="Tier2-B",
        input_fields=["enlistment_date", "branch"],
        output_fields=["discharge_date", "remaining_days", "progress_pct"],
        formula=None,
        formula_status="operator_confirmed",
        scope_exclusions=[],
        test_cases=[],
        desc="",
        legal_refs=["military_service_act_18", "military_service_act_30"],
    )
    hold = check_hold_rules(contract)
    assert "HOLD-3" in hold.get("rules", []), (
        "military_service_act_18/30은 confidence=medium → HOLD-3가 발동해야 함"
    )


# ─── 5. _build_tier2b_app 반환 필드 검증 ────────────────────────────────────────

def test_build_tier2b_app_returns_required_fields():
    contract = {
        "name": "군인 전역일 계산기",
        "category": "병역/공무",
        "slug": "military-discharge-date",
        "desc": "테스트 설명",
        "tier": "Tier2-B",
    }
    app = _build_tier2b_app(contract)
    assert app["html"], "html 필드가 비어있음"
    assert app["calculator_type"] == "date_based"
    assert app["compute_type"] == "date_based_custom"
    assert app["tier"] == 2
    assert "_tokens" in app
    assert "_steps" in app
    assert app.get("_formula_valid") is True
    assert "enlistment_date" in app["input_schema"]
    assert "discharge_date" in app["output_schema"]
    assert "병무청 확인" in app["html"], "면책 문구(병무청 확인) 미포함"
    assert "참고용" in app["html"], "면책 문구(참고용) 미포함"
