# -*- coding: utf-8 -*-
"""tests/test_unemployment_benefit_compute.py — 실업급여 computeResult 회귀 테스트 (영구 등록)

Phase 1 (2026-07-19) 구현 내용:
  UB-1(major): avg_daily_wage ≤ 0 → None
  UB-3(critical): employment_months < 6 → 수급 불가 (고용보험법 제40조 피보험단위기간 180일)
  UB-4(critical): 상한 클램프 = 66,000원/일 (고용노동부 고시)
  UB-5(critical): 하한 클램프 = 최저임금 × 8 × 0.8 (고용보험법 제46조 제2항)
  소정급여일수 2차원 테이블 (고용보험법 별표1, 2019년 개정 이후 현행)
  total_benefit 출력

수치 갱신 방법:
  DAILY_MAX, MIN_WAGE_HOURLY → docs/legal_basis.draft.yaml unemployment-benefit.benefit_amounts
  갱신 후 이 파일의 DAILY_MAX, MIN_WAGE_HOURLY, DAILY_MIN 상수도 동기화.

패턴 참고: tests/test_severance_compute.py (퇴직금 동일 구조)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

# ── 상수: legal_basis.draft.yaml unemployment-benefit.benefit_amounts와 동기화 필요 ──
DAILY_MAX = 66_000            # 고용노동부 고시 (2025년 기준)
MIN_WAGE_HOURLY = 10_030      # 최저임금 시간급 (2025년 기준)
DAILY_MIN = round(MIN_WAGE_HOURLY * 8 * 0.8)   # = 64,192원

# 소정급여일수 테이블 (고용보험법 별표1, 2019년 개정 이후)
_UNDER50 = [
    (0,   12,  120),
    (12,  36,  150),
    (36,  60,  180),
    (60,  120, 210),
    (120, None, 240),
]
_AGE50P = [
    (0,   12,  120),
    (12,  36,  180),
    (36,  60,  210),
    (60,  120, 240),
    (120, None, 270),
]


def _benefit_days(employment_months: int, age: int) -> int:
    table = _AGE50P if age >= 50 else _UNDER50
    for lo, hi, days in table:
        if employment_months >= lo and (hi is None or employment_months < hi):
            return days
    return table[-1][2]


def compute_ub(avg_daily_wage: float, age: int, employment_months: int) -> dict | None:
    """JS computeResult(unemployment-benefit) Python 미러.
    반환 None → JS null → "입력값을 확인해주세요" alert."""
    if avg_daily_wage <= 0 or age <= 0 or employment_months <= 0:
        return None

    out = {"notices": []}

    # UB-3: 피보험단위기간 6개월(약 180일) 미만 → 수급 불가
    if employment_months < 6:
        out["daily_benefit"] = 0
        out["benefit_days"] = 0
        out["total_benefit"] = 0
        out["notices"].append(
            "피보험단위기간이 180일(약 6개월) 미만이면 구직급여를 받을 수 없습니다 (고용보험법 제40조)."
        )
        out["_formula"] = f"{employment_months}개월 — 6개월 미만으로 수급 불가"
        return out

    raw_daily = avg_daily_wage * 0.6
    # UB-4/UB-5: 상한/하한 클램프
    daily_benefit = min(max(raw_daily, DAILY_MIN), DAILY_MAX)

    benefit_days = _benefit_days(employment_months, age)
    total_benefit = daily_benefit * benefit_days

    out["daily_benefit"] = daily_benefit
    out["benefit_days"] = benefit_days
    out["total_benefit"] = total_benefit

    if raw_daily < DAILY_MIN:
        out["notices"].append(
            f"일 구직급여가 하한({DAILY_MIN:,}원)보다 낮아 하한액이 적용됩니다 (고용보험법 제46조 제2항)."
        )
    elif raw_daily > DAILY_MAX:
        out["notices"].append(
            f"일 구직급여가 상한({DAILY_MAX:,}원)을 초과하여 상한액이 적용됩니다 (고용노동부 고시)."
        )

    out["_formula"] = (
        f"{avg_daily_wage:,.0f}원 × 0.6 = {round(raw_daily):,}원 → "
        f"클램프 = {round(daily_benefit):,}원/일 × {benefit_days}일 = {round(total_benefit):,}원"
    )
    return out


# ── pytest 개별 테스트 ────────────────────────────────────────────────────────

def test_zero_wage_returns_none():
    """UB-1: avg_daily_wage = 0 → None."""
    assert compute_ub(0, 40, 24) is None


def test_negative_wage_returns_none():
    """UB-1: avg_daily_wage < 0 → None."""
    assert compute_ub(-50000, 40, 24) is None


def test_zero_age_returns_none():
    """입력 검증: age = 0 → None."""
    assert compute_ub(80000, 0, 24) is None


def test_zero_months_returns_none():
    """입력 검증: employment_months = 0 → None."""
    assert compute_ub(80000, 40, 0) is None


def test_5months_ineligible():
    """UB-3: 5개월 → 수급 불가, daily_benefit=0, total_benefit=0, notice 포함."""
    r = compute_ub(100_000, 40, 5)
    assert r is not None
    assert r["daily_benefit"] == 0
    assert r["benefit_days"] == 0
    assert r["total_benefit"] == 0
    assert len(r["notices"]) > 0
    assert "고용보험법 제40조" in r["notices"][0]


def test_6months_boundary_eligible():
    """UB-3 경계: 6개월 → 수급 가능, 120일, 하한 클램프 적용."""
    r = compute_ub(100_000, 40, 6)
    assert r is not None
    assert r["benefit_days"] == 120
    assert r["daily_benefit"] == DAILY_MIN
    assert r["total_benefit"] == DAILY_MIN * 120


def test_under_floor_clamps_to_min():
    """UB-5: raw_daily < DAILY_MIN → daily_benefit = DAILY_MIN."""
    r = compute_ub(80_000, 40, 24)   # raw=48000 < 64192
    assert r is not None
    assert r["daily_benefit"] == DAILY_MIN
    assert any("하한" in n for n in r["notices"])


def test_over_ceiling_clamps_to_max():
    """UB-4: raw_daily > DAILY_MAX → daily_benefit = DAILY_MAX."""
    r = compute_ub(120_000, 40, 24)  # raw=72000 > 66000
    assert r is not None
    assert r["daily_benefit"] == DAILY_MAX
    assert any("상한" in n for n in r["notices"])


def test_normal_no_clamp():
    """정상: raw_daily = DAILY_MAX → 클램프 없음, notice 없음."""
    r = compute_ub(DAILY_MAX / 0.6, 40, 24)
    assert r is not None
    assert r["daily_benefit"] == DAILY_MAX
    assert len(r["notices"]) == 0


def test_days_table_under50_12to36():
    """소정급여일수: 49세, 24개월 → 150일 (under50 두 번째 행)."""
    r = compute_ub(100_000, 49, 24)
    assert r is not None
    assert r["benefit_days"] == 150


def test_days_table_age50p_12to36():
    """소정급여일수: 50세, 24개월 → 180일 (age50p 두 번째 행)."""
    r = compute_ub(100_000, 50, 24)
    assert r is not None
    assert r["benefit_days"] == 180


def test_age_boundary_49_vs_50():
    """50세 경계: 49세=150일, 50세=180일 (동일 가입기간 24개월)."""
    r49 = compute_ub(100_000, 49, 24)
    r50 = compute_ub(100_000, 50, 24)
    assert r49["benefit_days"] == 150
    assert r50["benefit_days"] == 180


def test_days_table_under50_10years():
    """소정급여일수: 49세, 120개월 → 240일 (under50 최대)."""
    r = compute_ub(100_000, 49, 120)
    assert r is not None
    assert r["benefit_days"] == 240


def test_days_table_age50p_10years():
    """소정급여일수: 50세, 120개월 → 270일 (age50p 최대)."""
    r = compute_ub(100_000, 50, 120)
    assert r is not None
    assert r["benefit_days"] == 270


def test_total_benefit_computed():
    """total_benefit = daily_benefit × benefit_days."""
    r = compute_ub(100_000, 50, 24)   # 64192 × 180
    assert r is not None
    assert abs(r["total_benefit"] - DAILY_MIN * 180) < 0.01


def test_formula_string_populated():
    """_formula 문자열 생성 확인."""
    r = compute_ub(100_000, 40, 24)
    assert r is not None
    assert r.get("_formula") and "원" in r["_formula"]


# ── 독립 실행 (run_tests 요약 출력) ──────────────────────────────────────────

def run_tests():
    cases = [
        # (desc, wage, age, months, exp_null, exp_benefit_days, exp_notice_kw)
        ("0원 임금 → None",           0,        40, 24, True,  None, None),
        ("음수 임금 → None",          -1,        40, 24, True,  None, None),
        ("5개월 → 수급 불가",         100_000,  40,  5, False,    0, "고용보험법 제40조"),
        ("6개월(경계) → 120일",       100_000,  40,  6, False,  120, None),
        ("49세/24개월 → 150일",       100_000,  49, 24, False,  150, None),
        ("50세/24개월 → 180일",       100_000,  50, 24, False,  180, None),
        ("하한 클램프",                80_000,  40, 24, False,  150, "하한"),
        ("상한 클램프",               120_000,  40, 24, False,  150, "상한"),
        ("49세/120개월 → 240일",      100_000,  49,120, False,  240, None),
        ("50세/120개월 → 270일",      100_000,  50,120, False,  270, None),
    ]

    print("=" * 72)
    print(" 실업급여 computeResult 회귀 테스트 — 10케이스")
    print(f" DAILY_MAX={DAILY_MAX:,}원  DAILY_MIN={DAILY_MIN:,}원")
    print("=" * 72)

    all_ok = True
    for desc, wage, age, months, exp_null, exp_days, notice_kw in cases:
        r = compute_ub(wage, age, months)
        if exp_null:
            ok = r is None
        else:
            ok = r is not None
            if ok and exp_days is not None:
                ok = ok and r["benefit_days"] == exp_days
            if ok and notice_kw:
                ok = ok and any(notice_kw in n for n in r.get("notices", []))
        mark = "OK" if ok else "NG"
        if not ok:
            all_ok = False
        info = (f"days={r['benefit_days']} daily={r['daily_benefit']:,.0f} "
                f"total={r['total_benefit']:,.0f} notices={len(r.get('notices',[]))}건"
                if r else "None")
        print(f"[{mark}] {desc}")
        print(f"     wage={wage:,} age={age} months={months}  →  {info}")
        if r and r.get("_formula"):
            print(f"     _formula: {r['_formula']}")

    print()
    print("=" * 72)
    print("전체:", "ALL PASS" if all_ok else "FAIL 있음")
    return all_ok


if __name__ == "__main__":
    ok = run_tests()
    sys.exit(0 if ok else 1)
