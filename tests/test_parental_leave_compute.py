# -*- coding: utf-8 -*-
"""육아휴직급여 계산 엔진 테스트.

Python mirror: JS window.computeResult 1:1 재현 (test_severance_compute.py 패턴).
커버리지:
  - 피보험단위기간 경계 (179/180/181일)
  - 일반 육아휴직급여 (상한/정상/하한 경계)
  - 6+6 특례 (1~6개월 월별 상한)
  - 특례 종료 전환 구간 (6→7→8개월) — 지급률/상한/formula/notices 4가지 동시 전환
  - 입력 검증 (음수/0 → null)
  - 일반/특례 배타 조건
"""
import pytest

# ── 상수 (legal_basis.draft.yaml parental_leave_benefit 섹션과 동기화) ──────────
MIN_INSURED_DAYS = 180
GEN_RATE         = 0.80
GEN_CEILING      = 1_500_000
GEN_FLOOR        = 700_000
SP_RATE          = 1.00
SP_MAX_MONTHS    = 6
SP_CEILINGS      = [2_000_000, 2_500_000, 3_000_000, 3_500_000, 4_000_000, 4_500_000]

MODE_GENERAL = "GENERAL"
MODE_6PLUS6  = "SPECIAL_6_PLUS_6"


# ── Python mirror 함수 (JS computeResult 1:1 재현) ───────────────────────────

def determine_leave_mode(use_6plus6: int, leave_month: int) -> str:
    if use_6plus6 >= 1 and 1 <= leave_month <= SP_MAX_MONTHS:
        return MODE_6PLUS6
    return MODE_GENERAL


def calculate_general(wage: float) -> dict:
    raw     = wage * GEN_RATE
    applied = min(max(raw, GEN_FLOOR), GEN_CEILING)
    return {"raw": raw, "applied": applied,
            "ceiling": GEN_CEILING, "floor": GEN_FLOOR, "rate_pct": "80%"}


def calculate_6plus6(wage: float, leave_month: int) -> dict:
    raw     = wage * SP_RATE
    ceiling = SP_CEILINGS[leave_month - 1]
    applied = min(max(raw, GEN_FLOOR), ceiling)
    return {"raw": raw, "applied": applied,
            "ceiling": ceiling, "floor": GEN_FLOOR, "rate_pct": "100%"}


def compute_pl(monthly_wage: float, insured_days: int,
               use_6plus6: int, leave_month: int) -> dict | None:
    # ① 입력 검증
    if monthly_wage <= 0 or insured_days <= 0 or leave_month <= 0:
        return None

    out: dict = {"notices": []}

    # ② 수급자격 확인 (피보험단위기간 180일 — 고용보험법 제70조 제1항)
    if insured_days < MIN_INSURED_DAYS:
        out["monthly_allowance"] = 0
        out["notices"].append(
            f"피보험단위기간이 {insured_days}일로 180일 미만이면 육아휴직급여를 받을 수 없습니다"
            "(고용보험법 제70조 제1항)."
        )
        out["_formula"] = f"피보험단위기간 {insured_days}일 — 180일 미만으로 수급 불가"
        return out

    # ③ 판정
    mode = determine_leave_mode(use_6plus6, leave_month)

    # 7개월 이후 자동 일반 전환 notice
    if use_6plus6 >= 1 and leave_month > SP_MAX_MONTHS:
        out["notices"].append(
            f"6+6 특례는 1～{SP_MAX_MONTHS}개월에만 적용됩니다. "
            f"{leave_month}개월째는 일반 육아휴직급여(통상임금 80%)가 적용됩니다"
            "(고용보험법 시행령 제95조의2)."
        )

    # ④⑤⑥ 계산 실행 + 지급률 적용 + 상한·하한 클램프
    cr = calculate_6plus6(monthly_wage, leave_month) if mode == MODE_6PLUS6 \
         else calculate_general(monthly_wage)
    out["monthly_allowance"] = cr["applied"]

    # ⑦ notices: 상한·하한 적용 안내
    mode_notices = []
    if cr["raw"] > cr["ceiling"]:
        mode_notices.append(
            f"통상임금 기준 급여({round(cr['raw']):,}원)가 상한액({cr['ceiling']:,}원)을 "
            "초과하여 상한액이 적용됩니다(고용보험법 시행령 제95조)."
        )
    elif cr["raw"] < cr["floor"]:
        mode_notices.append(
            f"통상임금 기준 급여({round(cr['raw']):,}원)가 하한액({cr['floor']:,}원)보다 "
            "낮아 하한액이 적용됩니다(고용보험법 시행령 제95조)."
        )
    out["notices"] = out["notices"] + mode_notices

    # ⑧ _formula
    mode_label = f"6+6 특례 {leave_month}개월차" if mode == MODE_6PLUS6 else "일반"
    fs = (f"{mode_label} — 통상임금 {round(monthly_wage):,}원"
          f" × {cr['rate_pct']} = {round(cr['raw']):,}원")
    if cr["raw"] > cr["ceiling"]:
        fs += f" → 상한 적용({cr['ceiling']:,}원) → {round(cr['applied']):,}원"
    elif cr["raw"] < cr["floor"]:
        fs += f" → 하한 적용({cr['floor']:,}원) → {round(cr['applied']):,}원"
    out["_formula"] = fs

    # ⑨ 반환
    return out


# ── Unit tests: determine_leave_mode ─────────────────────────────────────────

def test_mode_general_when_not_special():
    assert determine_leave_mode(0, 1)  == MODE_GENERAL
    assert determine_leave_mode(0, 6)  == MODE_GENERAL
    assert determine_leave_mode(0, 12) == MODE_GENERAL

def test_mode_6plus6_when_special_month_1_to_6():
    for mo in range(1, 7):
        assert determine_leave_mode(1, mo) == MODE_6PLUS6, f"month={mo}"

def test_mode_general_when_special_month_over_6():
    assert determine_leave_mode(1, 7)  == MODE_GENERAL
    assert determine_leave_mode(1, 8)  == MODE_GENERAL
    assert determine_leave_mode(1, 12) == MODE_GENERAL


# ── Unit tests: calculate_general ────────────────────────────────────────────

def test_general_ceiling_applied():
    cr = calculate_general(3_000_000)  # 300만 × 80% = 240만 > 150만(상한)
    assert cr["applied"] == 1_500_000
    assert cr["raw"] == pytest.approx(2_400_000)

def test_general_ceiling_exact_boundary():
    # 통상임금 1,875,000원 → 80% = 1,500,000 = 상한 정확히 (클램프 X)
    cr = calculate_general(1_875_000)
    assert cr["raw"] == pytest.approx(1_500_000)
    assert cr["applied"] == 1_500_000

def test_general_no_clamp():
    cr = calculate_general(1_800_000)  # 180만 × 80% = 144만 (상한 미만)
    assert cr["applied"] == pytest.approx(1_440_000)

def test_general_floor_exact_boundary():
    # 통상임금 875,000원 → 80% = 700,000 = 하한 정확히 (클램프 X)
    cr = calculate_general(875_000)
    assert cr["raw"] == pytest.approx(700_000)
    assert cr["applied"] == 700_000

def test_general_floor_applied():
    cr = calculate_general(800_000)  # 80만 × 80% = 64만 < 70만(하한)
    assert cr["applied"] == 700_000
    assert cr["raw"] == pytest.approx(640_000)


# ── Unit tests: calculate_6plus6 ─────────────────────────────────────────────

@pytest.mark.parametrize("month,wage,expected", [
    (1, 3_000_000, 2_000_000),   # 300만×100%=300만 > 200만(상한) → 200만
    (2, 3_000_000, 2_500_000),   # 300만 > 250만 → 250만
    (3, 3_000_000, 3_000_000),   # 300만 = 300만(상한) → 300만 (정확히 상한, 클램프 X)
    (4, 3_000_000, 3_000_000),   # 300만 < 350만 → 300만
    (5, 3_000_000, 3_000_000),   # 300만 < 400만 → 300만
    (6, 3_000_000, 3_000_000),   # 300만 < 450만 → 300만
    (6, 5_000_000, 4_500_000),   # 500만 > 450만 → 450만(상한)
    (1, 700_000,   700_000),     # 70만×100%=70만 = 하한 → 70만
    (1, 600_000,   700_000),     # 60만 < 70만(하한) → 70만(하한)
])
def test_6plus6_monthly_ceilings(month, wage, expected):
    cr = calculate_6plus6(wage, month)
    assert cr["applied"] == expected, f"month={month}, wage={wage:,}"


# ── Integration tests: compute_pl ────────────────────────────────────────────

# ── 입력 검증 ────────────────────────────────────────────────────────────────

def test_null_on_zero_wage():
    assert compute_pl(0, 180, 0, 1) is None

def test_null_on_negative_wage():
    assert compute_pl(-1_000_000, 180, 0, 1) is None

def test_null_on_zero_insured_days():
    assert compute_pl(3_000_000, 0, 0, 1) is None

def test_null_on_zero_leave_month():
    assert compute_pl(3_000_000, 180, 0, 0) is None


# ── 피보험단위기간 경계 (PL-12) ──────────────────────────────────────────────

def test_insured_days_179_ineligible():
    r = compute_pl(3_000_000, 179, 0, 1)
    assert r is not None
    assert r["monthly_allowance"] == 0
    assert any("179일" in n for n in r["notices"])
    assert any("180일 미만" in n for n in r["notices"])
    assert "180일 미만" in r["_formula"]

def test_insured_days_180_eligible():
    r = compute_pl(3_000_000, 180, 0, 1)
    assert r is not None
    assert r["monthly_allowance"] > 0

def test_insured_days_181_eligible():
    r = compute_pl(3_000_000, 181, 0, 1)
    assert r is not None
    assert r["monthly_allowance"] > 0


# ── 일반 육아휴직급여 ─────────────────────────────────────────────────────────

def test_general_ceiling_notice():
    r = compute_pl(3_000_000, 180, 0, 1)
    assert r["monthly_allowance"] == 1_500_000
    assert any("상한액" in n for n in r["notices"])
    assert "상한 적용" in r["_formula"]

def test_general_normal():
    r = compute_pl(1_800_000, 180, 0, 1)
    assert r["monthly_allowance"] == pytest.approx(1_440_000)
    assert not any("상한액" in n for n in r["notices"])
    assert not any("하한액" in n for n in r["notices"])

def test_general_floor_notice():
    r = compute_pl(800_000, 180, 0, 1)
    assert r["monthly_allowance"] == 700_000
    assert any("하한액" in n for n in r["notices"])
    assert "하한 적용" in r["_formula"]

def test_general_formula_contains_80pct():
    r = compute_pl(1_500_000, 180, 0, 3)
    assert "80%" in r["_formula"]
    assert "일반" in r["_formula"]


# ── 6+6 특례 ─────────────────────────────────────────────────────────────────

def test_special_month1_ceiling():
    r = compute_pl(3_000_000, 180, 1, 1)
    assert r["monthly_allowance"] == 2_000_000
    assert any("상한액" in n for n in r["notices"])
    assert "6+6 특례 1개월차" in r["_formula"]
    assert "100%" in r["_formula"]

def test_special_month6_no_ceiling():
    r = compute_pl(4_000_000, 180, 1, 6)
    assert r["monthly_allowance"] == 4_000_000  # 400만 < 450만 → 클램프 없음
    assert not any("상한액" in n for n in r["notices"])
    assert "6+6 특례 6개월차" in r["_formula"]

def test_special_month6_ceiling():
    r = compute_pl(5_000_000, 180, 1, 6)
    assert r["monthly_allowance"] == 4_500_000
    assert any("상한액" in n for n in r["notices"])

@pytest.mark.parametrize("month", range(1, 7))
def test_special_each_month_ceiling(month):
    expected_ceil = SP_CEILINGS[month - 1]
    r = compute_pl(10_000_000, 180, 1, month)  # 통상임금 1천만 → 항상 상한 초과
    assert r["monthly_allowance"] == expected_ceil


# ── 특례 종료 전환 구간 (핵심 경계 테스트: 6→7→8개월) ───────────────────────
# 지급률 / 상한 / formula / notices 4가지 동시 전환 확인

def test_special_transition_6_to_7_rate_and_ceiling():
    wage = 3_000_000
    r6 = compute_pl(wage, 180, 1, 6)
    r7 = compute_pl(wage, 180, 1, 7)

    # 지급률 전환: 100% → 80%
    assert "100%" in r6["_formula"]
    assert "80%"  in r7["_formula"]

    # 상한 전환: 450만 → 150만
    assert r6["monthly_allowance"] == 3_000_000  # 300만×100% < 450만 → 300만
    assert r7["monthly_allowance"] == 1_500_000  # 300만×80%=240만 > 150만 → 150만

def test_special_transition_6_to_7_formula():
    wage = 3_000_000
    r6 = compute_pl(wage, 180, 1, 6)
    r7 = compute_pl(wage, 180, 1, 7)

    # formula 전환: "6+6 특례 6개월차" → "일반"
    assert "6+6 특례 6개월차" in r6["_formula"]
    assert "일반" in r7["_formula"]
    assert "6+6" not in r7["_formula"]

def test_special_transition_6_to_7_notices():
    wage = 3_000_000
    r6 = compute_pl(wage, 180, 1, 6)
    r7 = compute_pl(wage, 180, 1, 7)

    # 6개월: 전환 notice 없음
    assert not any("7개월" in n for n in r6["notices"])

    # 7개월: 자동 일반 전환 notice 있음
    assert any("7개월" in n for n in r7["notices"])
    assert any("일반 육아휴직급여" in n for n in r7["notices"])

def test_special_transition_month8_still_general():
    r8 = compute_pl(3_000_000, 180, 1, 8)
    assert "일반" in r8["_formula"]
    assert "80%" in r8["_formula"]
    assert r8["monthly_allowance"] == 1_500_000
    assert any("8개월" in n for n in r8["notices"])

def test_special_transition_all_four_aspects():
    """6→7개월: 지급률/상한/formula/notices 4가지 동시 전환 종합 검증."""
    wage = 3_000_000
    r6 = compute_pl(wage, 180, 1, 6)
    r7 = compute_pl(wage, 180, 1, 7)

    # ① 지급률
    assert "100%" in r6["_formula"]
    assert "80%"  in r7["_formula"]
    # ② 상한
    assert r6["monthly_allowance"] == 3_000_000
    assert r7["monthly_allowance"] == 1_500_000
    # ③ formula 라벨
    assert "6+6 특례 6개월차" in r6["_formula"]
    assert "일반" in r7["_formula"]
    # ④ notices
    transition_notices_7 = [n for n in r7["notices"] if "7개월" in n]
    assert len(transition_notices_7) == 1


# ── 일반/특례 배타 조건 ─────────────────────────────────────────────────────

def test_general_no_transition_notice_when_use_6plus6_is_0():
    r = compute_pl(3_000_000, 180, 0, 7)  # use_6plus6=0 → 그냥 일반, 전환 notice 없음
    assert not any("특례" in n for n in r["notices"])
    assert "일반" in r["_formula"]

def test_special_not_applied_when_use_6plus6_0():
    r = compute_pl(3_000_000, 180, 0, 1)
    assert "일반" in r["_formula"]
    assert "80%" in r["_formula"]


# ── 정부 기준 케이스 (참조: parental_leave_2026.md) ─────────────────────────

@pytest.mark.parametrize("wage,ins,use_sp,month,expected", [
    # 일반
    (3_000_000, 365, 0, 1, 1_500_000),    # 상한 적용
    (1_875_000, 365, 0, 1, 1_500_000),    # 정확히 상한 (= 상한, 클램프 포함)
    (1_800_000, 365, 0, 1, 1_440_000),    # 정상 구간
    (875_000,   365, 0, 1, 700_000),      # 정확히 하한
    (800_000,   365, 0, 1, 700_000),      # 하한 적용
    # 6+6 특례
    (3_000_000, 365, 1, 1, 2_000_000),   # 1개월 상한 적용
    (1_500_000, 365, 1, 1, 1_500_000),   # 1개월 정상
    (3_000_000, 365, 1, 3, 3_000_000),   # 3개월 정확히 상한
    (4_000_000, 365, 1, 6, 4_000_000),   # 6개월 정상
    (5_000_000, 365, 1, 6, 4_500_000),   # 6개월 상한 적용
])
def test_government_reference_cases(wage, ins, use_sp, month, expected):
    r = compute_pl(wage, ins, use_sp, month)
    assert r is not None
    assert r["monthly_allowance"] == pytest.approx(expected), \
        f"wage={wage:,}, month={month}, use_sp={use_sp} → {r['monthly_allowance']:,} (expected {expected:,})"
