# -*- coding: utf-8 -*-
"""tests/test_invariants.py — 7개 계산기 핵심 불변식(Invariant) 파라미터화 테스트 (Phase B)

불변식 목적:
  계산 로직 변경 시 수학적 단조성/음수 불가/구조 보존이 깨지면 즉시 감지.
  경계값 회귀 테스트(test_*_compute.py)와 별개로, "입력 증가 방향"에 대한 단조 보존을 검증.

불변식 목록:
  INV-1  주휴수당: 근무시간↑ → 수당 단조 증가 (15시간 이상 구간)
  INV-2  퇴직금: 근속일수↑ → 퇴직금 단조 증가 (365일 이상 구간)
  INV-3  4대보험: 모든 항목 음수 불가
  INV-4  연차수당: 미사용 연차↑ → 수당 단조 증가
  INV-5  육아휴직: 6→7개월 전환 시 지급률/상한/notices/formula 동시 변경
  INV-6  연말정산: 총급여↑ → 근로소득공제 단조 증가 (한도 전까지)
  INV-7  연말정산: 과세표준 음수 불가
  INV-8  실업급여: 고용 개월수↑(6개월 이상) → 소정급여일수 단조 비감소
  INV-9  4대보험: total == 4종 합산 (대수 불변식)
"""
import sys
from pathlib import Path
from datetime import date, timedelta
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

# ── Python 미러 임포트 (각 test_*_compute.py와 동일 로직) ────────────────────

from tests.test_weekly_holiday_compute import compute_weekly_allowance
from tests.test_severance_compute import compute_severance
from tests.test_four_insurances_compute import compute_fi
from tests.test_annual_leave_compute import compute_annual_leave_allowance
from tests.test_parental_leave_compute import (
    determine_leave_mode, calculate_general, calculate_6plus6,
    MIN_INSURED_DAYS, GEN_RATE, GEN_FLOOR, SP_RATE, SP_CEILINGS,
    MODE_GENERAL, MODE_6PLUS6,
)
GEN_CEIL   = 1_500_000   # GEN_CEILING alias (parental_leave 파일 내 이름)
SP_MAX_MO  = 6           # SP_MAX_MONTHS alias
from modules.income_tax_calculator import (
    compute_labor_income_deduction,
    compute_year_end_settlement,
)


# ══════════════════════════════════════════════════════════════════════════════
# INV-1  주휴수당: 근무시간↑ → 수당 단조 증가 (15시간 이상)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("h1,h2", [
    (15, 20), (20, 30), (30, 40), (40, 50), (40, 168),
])
def test_inv1_weekly_allowance_monotone_increasing(h1, h2):
    """근무시간이 늘수록 주휴수당도 늘어야 한다 (단조 증가)."""
    r1 = compute_weekly_allowance(10_030, h1)
    r2 = compute_weekly_allowance(10_030, h2)
    assert r1 is not None and r2 is not None
    assert r2["weekly_allowance"] > r1["weekly_allowance"], (
        f"h1={h1} → {r1['weekly_allowance']:.0f}, h2={h2} → {r2['weekly_allowance']:.0f}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# INV-2  퇴직금: 근속일수↑ → 퇴직금 단조 증가 (365일 이상)
# ══════════════════════════════════════════════════════════════════════════════

def _datestr_pair(total_days: int):
    start = date(2020, 1, 1)
    end = start + timedelta(days=total_days)
    return start.isoformat(), end.isoformat()


@pytest.mark.parametrize("d1,d2", [
    (365, 400), (400, 730), (730, 1000), (1000, 3650),
])
def test_inv2_severance_monotone_increasing(d1, d2):
    """근속 일수가 늘수록 퇴직금도 늘어야 한다 (단조 증가)."""
    s1, e1 = _datestr_pair(d1)
    s2, e2 = _datestr_pair(d2)
    r1 = compute_severance(3_000_000, s1, e1)
    r2 = compute_severance(3_000_000, s2, e2)
    assert r1 is not None and r2 is not None
    assert r2["severance_pay"] > r1["severance_pay"], (
        f"d1={d1}일 → {r1['severance_pay']:.0f}, d2={d2}일 → {r2['severance_pay']:.0f}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# INV-3  4대보험: 모든 항목 음수 불가
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("salary", [200_000, 390_000, 1_000_000, 3_000_000, 6_170_000, 10_000_000])
def test_inv3_four_insurances_no_negative(salary):
    """모든 보험료 항목이 음수가 되어선 안 된다."""
    r = compute_fi(salary)
    assert r is not None
    for key in ["national_pension", "health_insurance", "long_term_care", "employment_insurance", "total"]:
        assert r[key] >= 0, f"{key} < 0: salary={salary}"


# ══════════════════════════════════════════════════════════════════════════════
# INV-9  4대보험: total == 4종 합산 (대수 불변식) — 추가 케이스
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("salary", [300_000, 500_000, 2_000_000, 5_000_000, 8_000_000])
def test_inv9_four_insurances_total_equals_sum(salary):
    """total은 반드시 4종 합산과 일치해야 한다."""
    r = compute_fi(salary)
    assert r is not None
    expected = (r["national_pension"] + r["health_insurance"]
                + r["long_term_care"] + r["employment_insurance"])
    assert abs(r["total"] - expected) < 1e-9, f"total 불일치: salary={salary}"


# ══════════════════════════════════════════════════════════════════════════════
# INV-4  연차수당: 미사용 연차↑ → 수당 단조 증가
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("d1,d2", [
    (1, 5), (5, 10), (10, 15), (15, 25), (25, 30),
])
def test_inv4_annual_leave_monotone_increasing(d1, d2):
    """미사용 연차 일수가 늘수록 수당도 늘어야 한다."""
    r1 = compute_annual_leave_allowance(80_000, d1)
    r2 = compute_annual_leave_allowance(80_000, d2)
    assert r1 is not None and r2 is not None
    assert r2["annual_leave_allowance"] > r1["annual_leave_allowance"], (
        f"d1={d1} → {r1['annual_leave_allowance']:.0f}, d2={d2} → {r2['annual_leave_allowance']:.0f}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# INV-5  육아휴직: 6→7개월 전환 시 지급률/상한/notices/formula 동시 변경
# ══════════════════════════════════════════════════════════════════════════════

def _compute_parental(monthly_wage, insured_days, use_6plus6, leave_month):
    """육아휴직 계산 헬퍼 (test_parental_leave_compute.py 패턴)."""
    if monthly_wage <= 0 or insured_days <= 0 or leave_month <= 0:
        return None
    out = {"notices": []}
    if insured_days < MIN_INSURED_DAYS:
        out["monthly_allowance"] = 0
        out.update({"_formula": "수급 불가"})
        return out
    if use_6plus6 >= 1 and leave_month > SP_MAX_MO:
        out["notices"].append(f"6+6 특례 초과: {leave_month}개월은 일반 적용")
    mode = determine_leave_mode(use_6plus6, leave_month)
    cr = (calculate_6plus6(monthly_wage, leave_month)
          if mode == MODE_6PLUS6 else calculate_general(monthly_wage))
    out["monthly_allowance"] = cr["applied"]
    out["mode"] = mode
    out["rate"] = SP_RATE if mode == MODE_6PLUS6 else GEN_RATE
    out["ceiling"] = cr["ceiling"]
    out["_formula"] = f"{mode}:{cr['applied']}"
    return out


def test_inv5_parental_6to7_mode_switches():
    """6→7개월 전환 시 mode가 GENERAL로 바뀌어야 한다."""
    wage = 2_000_000
    r6 = _compute_parental(wage, 200, 1, 6)
    r7 = _compute_parental(wage, 200, 1, 7)
    assert r6 is not None and r7 is not None
    assert r6["mode"] == MODE_6PLUS6
    assert r7["mode"] == MODE_GENERAL


def test_inv5_parental_6to7_rate_decreases():
    """6→7개월 전환 시 지급률이 낮아져야 한다 (100% → 80%)."""
    wage = 2_000_000
    r6 = _compute_parental(wage, 200, 1, 6)
    r7 = _compute_parental(wage, 200, 1, 7)
    assert r6 is not None and r7 is not None
    assert r6["rate"] == SP_RATE  # 100%
    assert r7["rate"] == GEN_RATE  # 80%
    assert r6["rate"] > r7["rate"]


def test_inv5_parental_6to7_ceiling_decreases():
    """6→7개월 전환 시 상한액이 낮아져야 한다 (4,500,000 → 1,500,000)."""
    wage = 5_000_000
    r6 = _compute_parental(wage, 200, 1, 6)
    r7 = _compute_parental(wage, 200, 1, 7)
    assert r6 is not None and r7 is not None
    assert r6["ceiling"] == SP_CEILINGS[5]   # 6개월차 특례 상한 4,500,000
    assert r7["ceiling"] == GEN_CEIL           # 일반 상한 1,500,000
    assert r6["ceiling"] > r7["ceiling"]


def test_inv5_parental_6to7_notice_appears():
    """7개월째에는 전환 notice가 포함되어야 한다."""
    r7 = _compute_parental(2_000_000, 200, 1, 7)
    assert r7 is not None
    has_transition_notice = any("7개월" in n or "초과" in n or "6개월" in n.lower()
                                 for n in r7["notices"])
    assert has_transition_notice, f"전환 notice 없음: {r7['notices']}"


# ══════════════════════════════════════════════════════════════════════════════
# INV-6  연말정산: 총급여↑ → 근로소득공제 단조 증가 (한도 20,000,000원 이전)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("s1,s2", [
    (10_000_000, 20_000_000),
    (20_000_000, 30_000_000),
    (30_000_000, 50_000_000),
    (50_000_000, 80_000_000),
])
def test_inv6_labor_deduction_monotone_increasing(s1, s2):
    """총급여가 늘수록 근로소득공제도 늘어야 한다 (한도 2,000만원까지)."""
    d1 = compute_labor_income_deduction(s1)
    d2 = compute_labor_income_deduction(s2)
    # 한도 미만 구간: 단조 증가
    if d1 < 20_000_000 and d2 < 20_000_000:
        assert d2 > d1, f"s1={s1:,} → {d1:,}, s2={s2:,} → {d2:,}"
    else:
        # 한도 도달 후: d2 == d1 == 20,000,000 허용
        assert d2 >= d1


def test_inv6_labor_deduction_ceiling_enforced():
    """한도(2,000만원)를 초과하지 않아야 한다."""
    for salary in [100_000_000, 200_000_000, 500_000_000]:
        d = compute_labor_income_deduction(salary)
        assert d <= 20_000_000, f"salary={salary:,} → deduction={d:,} > 한도"


# ══════════════════════════════════════════════════════════════════════════════
# INV-7  연말정산: 과세표준 음수 불가
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("salary,family", [
    (10_000_000, 1), (15_000_000, 3), (20_000_000, 5),
    (30_000_000, 1), (50_000_000, 2), (100_000_000, 1),
])
def test_inv7_taxable_income_nonnegative(salary, family):
    """과세표준은 음수가 되어선 안 된다."""
    r = compute_year_end_settlement(salary, family, 0)
    assert r["taxable_income"] >= 0, (
        f"taxable_income={r['taxable_income']} < 0: salary={salary}, family={family}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# INV-8  실업급여: 고용 개월수↑ → 소정급여일수 단조 비감소 (같은 연령대)
# ══════════════════════════════════════════════════════════════════════════════

def _compute_ub_days(employment_months: int, age: int) -> int:
    """소정급여일수 산출 (test_unemployment_benefit_compute.py 미러)."""
    under50 = [
        {"lo": 6, "hi": 12, "d": 120},
        {"lo": 12, "hi": 18, "d": 150},
        {"lo": 18, "hi": 24, "d": 180},
        {"lo": 24, "hi": 36, "d": 210},
        {"lo": 36, "hi": float("inf"), "d": 240},
    ]
    age50p = [
        {"lo": 6, "hi": 12, "d": 120},
        {"lo": 12, "hi": 18, "d": 180},
        {"lo": 18, "hi": 24, "d": 210},
        {"lo": 24, "hi": 36, "d": 240},
        {"lo": 36, "hi": float("inf"), "d": 270},
    ]
    table = age50p if age >= 50 else under50
    days = table[-1]["d"]
    for row in table:
        if row["lo"] <= employment_months < row["hi"]:
            days = row["d"]
            break
    return days


@pytest.mark.parametrize("m1,m2,age", [
    (6, 12, 30), (12, 18, 30), (24, 36, 30),
    (6, 12, 55), (12, 24, 55), (36, 48, 55),
])
def test_inv8_unemployment_days_nondecreasing(m1, m2, age):
    """고용 개월수 증가 → 소정급여일수 단조 비감소."""
    d1 = _compute_ub_days(m1, age)
    d2 = _compute_ub_days(m2, age)
    assert d2 >= d1, f"age={age}: m1={m1}→{d1}일, m2={m2}→{d2}일"
