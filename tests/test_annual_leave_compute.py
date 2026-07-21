# -*- coding: utf-8 -*-
"""tests/test_annual_leave_compute.py — 연차수당 computeResult 회귀 테스트 (영구 등록)

계산기 설계: 미사용 연차 일수 직접 입력 × 통상임금(일급) = 수당
법령: 근로기준법 제60조제5항(미사용 연차수당 청구권) / 제36조(퇴직 시 의무 지급) / 제61조(촉진제도)

커버리지:
  - 입력 검증 (음수/0 → null)
  - 법정 상한(25일) 초과 경고 notices
  - 단순 곱셈 정확성
  - SEO 예시 금액 교차 확인
  - _formula / notices 구조
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

LEGAL_MAX_DAYS = 25  # 근로기준법 제60조제4항 법정 상한


def compute_annual_leave_allowance(daily_wage: float, unused_days: float) -> dict | None:
    """JS computeResult(annual-leave-allowance) Python 미러."""
    if daily_wage <= 0 or unused_days <= 0:
        return None
    out = {}
    out["annual_leave_allowance"] = daily_wage * unused_days
    notices = []
    if unused_days > LEGAL_MAX_DAYS:
        notices.append(
            f"입력하신 미사용 연차({unused_days:.0f}일)가 법정 상한(25일)을 초과합니다. "
            "사용자가 추가로 부여한 약정 연차가 있는 경우 25일을 초과할 수 있습니다(근로기준법 제60조제4항)."
        )
    out["notices"] = notices
    out["_formula"] = (
        f"통상임금(일급) {daily_wage:,.0f}원 × {unused_days:.0f}일 = "
        f"{round(daily_wage * unused_days):,}원"
    )
    return out


# ── 입력 검증 ──────────────────────────────────────────────────────────────────

def test_zero_daily_wage_returns_none():
    assert compute_annual_leave_allowance(0, 5) is None


def test_negative_daily_wage_returns_none():
    assert compute_annual_leave_allowance(-80_000, 5) is None


def test_zero_unused_days_returns_none():
    assert compute_annual_leave_allowance(80_000, 0) is None


def test_negative_unused_days_returns_none():
    assert compute_annual_leave_allowance(80_000, -1) is None


# ── 정상 계산 ─────────────────────────────────────────────────────────────────

def test_basic_calculation():
    r = compute_annual_leave_allowance(80_000, 5)
    assert r is not None
    assert r["annual_leave_allowance"] == 400_000.0


def test_formula_string_populated():
    r = compute_annual_leave_allowance(80_000, 5)
    assert r is not None
    assert "통상임금(일급)" in r["_formula"]
    assert "원" in r["_formula"]


def test_no_notices_for_normal_case():
    r = compute_annual_leave_allowance(80_000, 10)
    assert r is not None
    assert len(r["notices"]) == 0


def test_no_notices_at_legal_max():
    r = compute_annual_leave_allowance(80_000, 25)
    assert r is not None
    assert r["annual_leave_allowance"] == 80_000 * 25
    assert len(r["notices"]) == 0


# ── 법정 상한(25일) 초과 경고 ─────────────────────────────────────────────────

def test_notice_when_over_legal_max():
    r = compute_annual_leave_allowance(80_000, 26)
    assert r is not None
    assert r["annual_leave_allowance"] == 80_000 * 26
    assert len(r["notices"]) == 1
    assert "25일" in r["notices"][0]
    assert "초과" in r["notices"][0]


def test_notice_well_over_legal_max():
    r = compute_annual_leave_allowance(100_000, 30)
    assert r is not None
    assert r["annual_leave_allowance"] == 3_000_000.0
    assert any("초과" in n for n in r["notices"])


# ── SEO 예시 금액 교차 확인 ───────────────────────────────────────────────────

def test_seo_example_10_days():
    """SEO 예시: 일급 100,000원 × 10일 = 1,000,000원"""
    r = compute_annual_leave_allowance(100_000, 10)
    assert r is not None
    assert r["annual_leave_allowance"] == 1_000_000.0


def test_seo_example_5_days():
    """SEO 예시: 일급 80,000원 × 5일 = 400,000원"""
    r = compute_annual_leave_allowance(80_000, 5)
    assert r is not None
    assert r["annual_leave_allowance"] == 400_000.0


def test_seo_example_3_days():
    """SEO 예시: 일급 120,000원 × 3일 = 360,000원"""
    r = compute_annual_leave_allowance(120_000, 3)
    assert r is not None
    assert r["annual_leave_allowance"] == 360_000.0


# ── 경계값 3점 세트 (법정 상한) ───────────────────────────────────────────────

@pytest.mark.parametrize("days,expect_notice", [
    (24, False),
    (25, False),
    (26, True),
])
def test_legal_max_boundary_3point(days, expect_notice):
    r = compute_annual_leave_allowance(80_000, days)
    assert r is not None
    assert r["annual_leave_allowance"] == 80_000 * days
    has_notice = len(r["notices"]) > 0
    assert has_notice == expect_notice
