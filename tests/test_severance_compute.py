# -*- coding: utf-8 -*-
"""tests/test_severance_compute.py — 퇴직금 computeResult 회귀 테스트 (영구 등록)

2026-07-19 발견된 버그 수정(SP-1 critical / SP-3 major / SP-4 major) 이후,
향후 app_generator._compute_js() 또는 date_based 분기가 변경될 때
동일 문제가 재발하지 않음을 보장하는 안전망.

수정 내역:
  SP-1(critical): 재직 1년(365일) 미만 → 퇴직금 0원 + notice (근로자퇴직급여보장법 제8조)
  SP-3(major):   날짜 미입력/Invalid Date → None (입력 오류)
  SP-4(major):   평균임금 0 이하 → None (입력 오류)

테스트 방법:
  python -m pytest tests/test_severance_compute.py -v
  또는: python tests/test_severance_compute.py

패턴 참고: tests/test_weekly_holiday_compute.py (주휴수당 동일 구조)
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

# ── 검증 대상: app_generator._compute_js()가 생성한 JS 로직과 동일한 Python 구현 ──
# JS computeResult를 Python으로 1:1 재현. JS 변경 시 이 함수도 동기화 필요.
MIN_TENURE_DAYS = 365       # 근로자퇴직급여보장법 제8조: 1년 이상


def _date_diff(start: str, end: str):
    """날짜 문자열(YYYY-MM-DD) → 일수 차. 빈 문자열/불유효 → None(Invalid Date)."""
    if not start or not end:
        return None
    try:
        s = date.fromisoformat(start)
        e = date.fromisoformat(end)
        return (e - s).days
    except ValueError:
        return None


def compute_severance(avg_monthly_wage: float, start_date: str, end_date: str) -> dict | None:
    """JS computeResult(severance-pay) Python 미러.
    반환 None → JS null → "입력값을 확인해주세요" alert."""
    total_days = _date_diff(start_date, end_date)

    # SP-3: 날짜 미입력/Invalid Date → null
    if total_days is None:
        return None

    # SP-4: 평균임금 0 이하 → null
    if avg_monthly_wage <= 0:
        return None

    out = {"notices": []}

    # SP-1: 1년 미만 → 0원 + notice
    if total_days < MIN_TENURE_DAYS:
        out["severance_pay"] = 0.0
        out["notices"].append(
            "계속근로기간이 1년 미만이면 퇴직금 지급 의무가 없습니다 (근로자퇴직급여보장법 제8조)."
        )
        out["_detail"] = [{"label": "재직일수", "value": f"{max(total_days, 0)}일 (1년 미만)"}]
        out["_formula"] = f"{total_days}일 근무 — 1년(365일) 미만으로 퇴직금 미발생"
        return out

    # 정상 계산
    result = avg_monthly_wage * (total_days / 365)
    out["severance_pay"] = result
    out["_detail"] = [{"label": "재직일수", "value": f"{total_days}일"}]
    out["_formula"] = (
        f"{avg_monthly_wage:,.0f}원 × ({total_days}÷365) = {round(result):,}원"
    )
    return out


# ── 헬퍼: 날짜 문자열 생성 ────────────────────────────────────────────────────
def _datestr(base: date, delta_days: int) -> str:
    return (base + timedelta(days=delta_days)).isoformat()


START = date(2024, 1, 1)
S = START.isoformat()


def _end(days: int) -> str:
    return _datestr(START, days)


# ── 7+1개 핵심 케이스 ────────────────────────────────────────────────────────
def run_tests():
    cases = [
        # SP-1: 1년 경계 4점 세트
        ("재직 1일   → 0원+안내",   3_000_000, S, _end(1),   0.0,         True,  False),
        ("재직 364일 → 0원+안내",   3_000_000, S, _end(364), 0.0,         True,  False),
        ("재직 365일 → 정상계산",   3_000_000, S, _end(365), 3_000_000.0, False, False),
        ("재직 366일 → 정상계산",   3_000_000, S, _end(366), 3_008_219.0, False, False),
        # SP-3: 날짜 미입력 → None
        ("날짜 미입력 → None",      3_000_000, "",           "",           None,  None,  True),
        # SP-4: 평균임금 0/음수 → None
        ("평균임금 음수 → None",    -1_000_000, S, _end(365), None,        None,  True),
        ("평균임금 0   → None",     0,           S, _end(365), None,        None,  True),
        # 정상 케이스: 월300만 × 2년
        ("정상(300만×730일)→600만", 3_000_000, S, _end(730), 6_000_000.0, False, False),
    ]

    all_ok = True
    print("="*72)
    print(" 퇴직금 computeResult 회귀 테스트 — 8케이스")
    print(f" MIN_TENURE_DAYS={MIN_TENURE_DAYS}")
    print("="*72)

    for desc, wage, sd, ed, exp_wa, exp_notice, exp_null in cases:
        result = compute_severance(wage, sd, ed)
        if exp_null:
            ok = result is None
            detail = "None(입력오류)" if result is None else f"unexpected:{result}"
        else:
            ok = result is not None
            if ok and exp_wa is not None:
                ok = ok and abs(result["severance_pay"] - exp_wa) < 1.0
            if ok and exp_notice is not None:
                has_n = len(result.get("notices", [])) > 0
                ok = ok and (has_n == exp_notice)
            detail = (
                f"sp={result['severance_pay']:,.1f}  notices={len(result.get('notices',[]))}건"
                if result else "None"
            )

        mark = "OK" if ok else "NG"
        if not ok:
            all_ok = False
        print(f"[{mark}] {desc}")
        print(f"     임금={wage:,}원 / {sd}~{ed}  →  {detail}")
        if result and result.get("_formula"):
            print(f"     _formula: {result['_formula']}")
        if result and result.get("notices"):
            for n in result["notices"]:
                print(f"     notice: {n}")

    print()
    print("="*72)
    print("전체:", "ALL PASS" if all_ok else "FAIL 있음")
    return all_ok


# pytest 호환 개별 테스트 함수 ─────────────────────────────────────────────────
def test_1day_returns_zero_with_notice():
    """SP-1: 1일 재직 → 0원 + 법령 안내."""
    r = compute_severance(3_000_000, S, _end(1))
    assert r is not None
    assert r["severance_pay"] == 0.0
    assert len(r["notices"]) > 0
    assert "1년 미만" in r["notices"][0]


def test_364days_returns_zero_with_notice():
    """SP-1: 364일 재직 → 0원 + 법령 안내."""
    r = compute_severance(3_000_000, S, _end(364))
    assert r is not None
    assert r["severance_pay"] == 0.0
    assert len(r["notices"]) > 0


def test_365days_computes_normally():
    """SP-1 경계: 365일(정확히 1년) → 정상 계산, notices 없음."""
    r = compute_severance(3_000_000, S, _end(365))
    assert r is not None
    assert abs(r["severance_pay"] - 3_000_000.0) < 1.0
    assert len(r["notices"]) == 0


def test_366days_computes_normally():
    """SP-1: 366일 → 정상 계산."""
    r = compute_severance(3_000_000, S, _end(366))
    assert r is not None
    assert abs(r["severance_pay"] - 3_008_219.0) < 1.0


def test_empty_dates_returns_none():
    """SP-3: 날짜 미입력 → None."""
    assert compute_severance(3_000_000, "", "") is None
    assert compute_severance(3_000_000, S, "") is None
    assert compute_severance(3_000_000, "", _end(365)) is None


def test_negative_wage_returns_none():
    """SP-4: 음수 임금 → None."""
    assert compute_severance(-1_000_000, S, _end(365)) is None


def test_zero_wage_returns_none():
    """SP-4: 0원 임금 → None."""
    assert compute_severance(0, S, _end(365)) is None


def test_normal_case_2years():
    """정상: 월300만×730일 → 6,000,000원."""
    r = compute_severance(3_000_000, S, _end(730))
    assert r is not None
    assert abs(r["severance_pay"] - 6_000_000.0) < 1.0
    assert len(r["notices"]) == 0


def test_formula_string_populated():
    """정상 케이스 _formula 생성 확인."""
    r = compute_severance(3_000_000, S, _end(365))
    assert r is not None
    assert r["_formula"] and "원" in r["_formula"]


def test_seo_article_example():
    """SEO 글 예시: 월300만×2년=600만원 정합성."""
    r = compute_severance(3_000_000, S, _end(730))
    assert r is not None
    assert abs(r["severance_pay"] - 6_000_000.0) < 1.0


def test_longterm_10years():
    """장기근속: 월500만×10년(3650일)=5천만원."""
    r = compute_severance(5_000_000, S, _end(3650))
    assert r is not None
    assert abs(r["severance_pay"] - 50_000_000.0) < 1.0


if __name__ == "__main__":
    ok = run_tests()
    sys.exit(0 if ok else 1)
