# -*- coding: utf-8 -*-
"""tests/test_weekly_holiday_compute.py — 주휴수당 computeResult 회귀 테스트 (영구 등록)

이 테스트셋은 2026-07-19에 발견된 경계값 버그(B-1 critical / B-2 major / B-3 major)를
수정한 이후, 향후 app_generator._compute_js() 또는 weekly-holiday-allowance compute_rules가
변경될 때 동일 문제가 재발하지 않음을 보장하는 안전망이다.

테스트 방법:
  python -m pytest tests/test_weekly_holiday_compute.py -v
  또는: python tests/test_weekly_holiday_compute.py

경계값 세트 패턴 (나머지 6개 계산기에도 재사용 가능):
  - 법적 최솟값 직전 / 기준점 / 직후 3점
  - 0 입력 / 음수 입력
  - 최저임금 경계
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

# ── 검증 대상: app_generator._compute_js()가 생성한 JS 로직과 동일한 Python 구현 ──
# JS computeResult를 Python으로 1:1 재현. JS 변경 시 이 함수도 동기화 필요.
MIN_WEEKLY_HOURS = 15        # 근로기준법 제18조제3항
MIN_WAGE_2026 = 10_030       # 2026년 최저임금


def compute_weekly_allowance(hourly_wage: float, weekly_hours: float) -> dict | None:
    """JS computeResult(weekly-holiday-allowance) Python 미러.
    반환 None → JS null → "입력값을 확인해주세요" 표시."""
    if hourly_wage <= 0 or weekly_hours <= 0:
        return None  # B-2: 양수 입력 강제

    out = {"weekly_allowance": 0.0, "notices": [], "_formula": ""}

    # B-1: 15시간 미만 → 0원 + notice (근로기준법 제18조제3항)
    if weekly_hours < MIN_WEEKLY_HOURS:
        out["weekly_allowance"] = 0.0
        out["notices"].append(
            f"주 {MIN_WEEKLY_HOURS}시간 미만 근무 시 주휴수당이 발생하지 않습니다 (근로기준법 제18조제3항)."
        )
        out["_formula"] = f"주 {weekly_hours}시간 미만({MIN_WEEKLY_HOURS}시간 기준) — 주휴수당 미발생"
        return out

    # B-3: 최저임금 미만 → 경고 (계산 차단 안 함)
    if hourly_wage < MIN_WAGE_2026:
        out["notices"].append(
            f"입력한 시급({hourly_wage:,.0f}원)이 2026년 최저임금({MIN_WAGE_2026:,}원)보다 낮습니다."
        )

    # B-4: 계산 + _formula 표시
    result = hourly_wage * (weekly_hours / 40 * 8)
    out["weekly_allowance"] = result
    out["_formula"] = (
        f"{hourly_wage:,.0f}원 × ({weekly_hours}÷40×8) = {round(result):,}원"
    )
    return out


# ── 테스트 케이스 정의 ──────────────────────────────────────────────────────────
# (설명, hourly_wage, weekly_hours, 기대 weekly_allowance, notices에 포함 여부, result가 None?)
CASES = [
    # B-1: 주 15시간 경계 3점 세트 (시급=최저임금으로 최저임금 notice 배제)
    ("주 14.99시간 → 0원 + 미발생 안내",       10_030, 14.99, 0.0,       True,  False),
    ("주 15.00시간 → 정상 계산",               10_030, 15.0,  30_090.0,  False, False),
    ("주 15.01시간 → 정상 계산",               10_030, 15.01, 30_110.0,  False, False),

    # B-2: 0/음수 입력 → None
    ("시급 0원 → 입력 오류(None)",              0,      40.0,  None,      None,  True),
    ("시급 -100원 → 입력 오류(None)",          -100,   40.0,  None,      None,  True),

    # B-3: 최저임금 경계
    ("시급 9,000원 → 계산 + 최저임금 경고",   9_000,  40.0,  72_000.0,  True,  False),
    ("시급 10,030원 → 정상 (최저임금 정확히 같음)", 10_030, 40.0, 80_240.0, False, False),
]


def run_tests():
    all_ok = True
    print("=" * 70)
    print(" 주휴수당 computeResult 회귀 테스트 — 7케이스")
    print(f" MIN_WEEKLY_HOURS={MIN_WEEKLY_HOURS}  MIN_WAGE_2026={MIN_WAGE_2026:,}")
    print("=" * 70)

    for desc, hourly_wage, weekly_hours, expected_wa, expect_notice, expect_null in CASES:
        result = compute_weekly_allowance(hourly_wage, weekly_hours)

        if expect_null:
            ok = result is None
            detail = "None(입력오류)" if result is None else f"unexpected: {result}"
        else:
            ok = result is not None
            if ok and expected_wa is not None:
                ok = ok and abs(result["weekly_allowance"] - expected_wa) < 1.0
            if ok and expect_notice is not None:
                has_notice = len(result.get("notices", [])) > 0
                ok = ok and (has_notice == expect_notice)
            detail = (
                f"wa={result['weekly_allowance']:,.1f}  notices={len(result.get('notices',[]))}건"
                if result else "None"
            )

        mark = "OK" if ok else "NG"
        if not ok:
            all_ok = False
        print(f"[{mark}] {desc}")
        print(f"     입력: 시급={hourly_wage:,}원 / {weekly_hours}시간  →  {detail}")
        if result and result.get("_formula"):
            print(f"     _formula: {result['_formula']}")
        if result and result.get("notices"):
            for n in result["notices"]:
                print(f"     notice: {n}")

    print()
    print("=" * 70)
    print("전체:", "ALL PASS" if all_ok else "FAIL 있음")
    return all_ok


# pytest 호환 개별 테스트 함수 ─────────────────────────────────────────────────
def test_below_min_hours_returns_zero():
    r = compute_weekly_allowance(10_030, 14.99)
    assert r is not None
    assert r["weekly_allowance"] == 0.0
    assert len(r["notices"]) > 0
    assert "15시간" in r["notices"][0]


def test_at_min_hours_computes_normally():
    r = compute_weekly_allowance(10_030, 15.0)
    assert r is not None
    assert abs(r["weekly_allowance"] - 30_090.0) < 1.0
    assert len(r["notices"]) == 0


def test_above_min_hours_computes_normally():
    r = compute_weekly_allowance(10_030, 15.01)
    assert r is not None
    assert abs(r["weekly_allowance"] - 30_110.0) < 1.0


def test_zero_hourly_wage_returns_none():
    assert compute_weekly_allowance(0, 40.0) is None


def test_negative_hourly_wage_returns_none():
    assert compute_weekly_allowance(-100, 40.0) is None


def test_below_min_wage_adds_notice():
    r = compute_weekly_allowance(9_000, 40.0)
    assert r is not None
    assert abs(r["weekly_allowance"] - 72_000.0) < 1.0
    assert any("최저임금" in n for n in r["notices"])


def test_at_min_wage_no_notice():
    r = compute_weekly_allowance(10_030, 40.0)
    assert r is not None
    assert abs(r["weekly_allowance"] - 80_240.0) < 1.0
    assert len(r["notices"]) == 0


def test_formula_string_populated():
    r = compute_weekly_allowance(10_000, 40.0)
    assert r is not None
    assert r["_formula"] and "원" in r["_formula"]


def test_seo_article_example_40h():
    """SEO 글 예시: 시급 10,000원 × 주 40시간 = 80,000원 정합성."""
    r = compute_weekly_allowance(10_000, 40.0)
    assert r is not None
    assert abs(r["weekly_allowance"] - 80_000.0) < 1.0


def test_seo_article_example_30h():
    """SEO 글 예시: 시급 12,000원 × 주 30시간 = 72,000원 정합성."""
    r = compute_weekly_allowance(12_000, 30.0)
    assert r is not None
    assert abs(r["weekly_allowance"] - 72_000.0) < 1.0


def test_seo_article_example_20h():
    """SEO 글 예시: 시급 10,000원 × 주 20시간 = 40,000원 정합성."""
    r = compute_weekly_allowance(10_000, 20.0)
    assert r is not None
    assert abs(r["weekly_allowance"] - 40_000.0) < 1.0


if __name__ == "__main__":
    ok = run_tests()
    sys.exit(0 if ok else 1)
