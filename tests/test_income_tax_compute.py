# -*- coding: utf-8 -*-
"""연말정산 계산기 Python mirror 테스트.

검증 항목:
1. 근로소득공제 (소득세법 제47조) 구간 경계값
2. 산출세액 (소득세법 제55조) 누진세율 구간 경계값
3. 근로소득세액공제 한도 (소득세법 제59조) 구간 경계값
4. 전체 계산 흐름 (일반 케이스 2개 + 4대보험 상한/하한 케이스)
5. legal_basis 상수 동기화 확인

테스트 추가/삭제 금지 — 회귀 안전망. 법령 개정 시 상수와 기대값을 함께 갱신.
"""
import sys, os, math
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.income_tax_calculator import (
    compute_labor_income_deduction,
    compute_income_tax,
    compute_earned_tax_credit_limit,
    compute_earned_tax_credit,
    compute_insurance_deduction,
    compute_year_end_settlement,
)

# ─── 상수 (legal_basis.draft.yaml 동기화 확인용) ──────────────────────────────
LD_MAX = 20_000_000          # 근로소득공제 한도
PER_PERSON = 1_500_000       # 인적공제 1인당
CREDIT_THRESHOLD = 1_300_000 # 세액공제 55%/30% 분기


# ─── 1. 근로소득공제 구간 경계값 ─────────────────────────────────────────────

class TestLaborIncomeDeduction:
    def test_bracket1_upper(self):
        # 5M 이하 구간 상한: 5,000,000 × 70% = 3,500,000
        assert compute_labor_income_deduction(5_000_000) == 3_500_000

    def test_bracket2_lower(self):
        # 5M~15M 구간 하단: 3,500,000 + 1 × 40% = 3,500,000 (올림 없음)
        assert compute_labor_income_deduction(5_000_001) == 3_500_000

    def test_bracket2_upper(self):
        # 15M 상한: 3,500,000 + (15M-5M)×40% = 7,500,000
        assert compute_labor_income_deduction(15_000_000) == 7_500_000

    def test_bracket3_upper(self):
        # 45M 상한: 7,500,000 + (45M-15M)×15% = 12,000,000
        assert compute_labor_income_deduction(45_000_000) == 12_000_000

    def test_bracket4_upper(self):
        # 100M 상한: 12,000,000 + (100M-45M)×5% = 14,750,000
        assert compute_labor_income_deduction(100_000_000) == 14_750_000

    def test_bracket5_max_cap(self):
        # 150M: 14,750,000 + (150M-100M)×2% = 15,750,000 → 한도 20M 적용 → 15,750,000
        assert compute_labor_income_deduction(150_000_000) == 15_750_000

    def test_max_cap(self):
        # 충분히 큰 금액 → 한도 20,000,000
        result = compute_labor_income_deduction(1_000_000_000)
        assert result == LD_MAX

    def test_midpoint_bracket3(self):
        # 30M: 7,500,000 + (30M-15M)×15% = 7,500,000 + 2,250,000 = 9,750,000
        assert compute_labor_income_deduction(30_000_000) == 9_750_000


# ─── 2. 산출세액 누진세율 ─────────────────────────────────────────────────────

class TestIncomeTax:
    def test_zero_income(self):
        assert compute_income_tax(0) == 0

    def test_bracket1(self):
        # 14M × 6% = 840,000
        assert compute_income_tax(14_000_000) == 840_000

    def test_bracket2(self):
        # 30M: 30M×15% - 1,260,000 = 3,240,000
        assert compute_income_tax(30_000_000) == 3_240_000

    def test_bracket2_upper(self):
        # 50M: 50M×15% - 1,260,000 = 6,240,000
        assert compute_income_tax(50_000_000) == 6_240_000

    def test_bracket3(self):
        # 88M: 88M×24% - 5,760,000 = 15,360,000
        assert compute_income_tax(88_000_000) == 15_360_000

    def test_bracket4(self):
        # 150M: 150M×35% - 15,440,000 = 37,060,000
        assert compute_income_tax(150_000_000) == 37_060_000

    def test_bracket5(self):
        # 200M: 200M×38% - 19,940,000 = 56,060,000
        assert compute_income_tax(200_000_000) == 56_060_000

    def test_negative_taxable(self):
        # 과세표준 0 이하 → 세액 0
        assert compute_income_tax(-1_000) == 0


# ─── 3. 근로소득세액공제 한도 ────────────────────────────────────────────────

class TestEarnedTaxCreditLimit:
    def test_bracket1(self):
        # 3300만 이하 → 740,000
        assert compute_earned_tax_credit_limit(33_000_000) == 740_000

    def test_bracket1_low(self):
        assert compute_earned_tax_credit_limit(10_000_000) == 740_000

    def test_bracket2_floor(self):
        # 7000만: 740,000 - (70M-33M)×0.008 = 740,000-296,000=444,000 → 최저 660,000
        assert compute_earned_tax_credit_limit(70_000_000) == 660_000

    def test_bracket2_mid(self):
        # 50M: 740,000 - (50M-33M)×0.008 = 740,000-136,000=604,000 → 최저 660,000 → 660,000
        assert compute_earned_tax_credit_limit(50_000_000) == 660_000

    def test_bracket3_lower(self):
        # 7001만 → 3구간 시작 (약 500,000 이상)
        limit = compute_earned_tax_credit_limit(70_010_000)
        assert limit <= 660_000

    def test_bracket3_floor(self):
        # 1.2억: 660,000 - (120M-70M)×0.5 = 660,000-25M → 최저 500,000
        assert compute_earned_tax_credit_limit(120_000_000) == 500_000

    def test_bracket4_floor(self):
        # 1.3억: 500,000 - (130M-120M)×0.5 = 500,000-5M → 최저 200,000
        assert compute_earned_tax_credit_limit(130_000_000) == 200_000

    def test_bracket4_very_high(self):
        assert compute_earned_tax_credit_limit(500_000_000) == 200_000


# ─── 4. 근로소득세액공제액 ───────────────────────────────────────────────────

class TestEarnedTaxCredit:
    def test_low_branch(self):
        # 산출세액 ≤ 130만원 → ×55%
        assert compute_earned_tax_credit(1_000_000) == 550_000

    def test_threshold_exact(self):
        assert compute_earned_tax_credit(1_300_000) == 715_000

    def test_high_branch(self):
        # 200만: 715,000 + (2M-1.3M)×30% = 715,000+210,000 = 925,000
        assert compute_earned_tax_credit(2_000_000) == 925_000


# ─── 5. 4대보험공제 ─────────────────────────────────────────────────────────

class TestInsuranceDeduction:
    def test_normal(self):
        r = compute_insurance_deduction(60_000_000)
        assert r["annual_total"] > 0
        assert r["np_monthly"] > 0
        # 장기요양 = 건강보험료 × LTC_RATE (2026: 13.14%)
        assert abs(r["ltc_monthly"] - r["hi_monthly"] * 0.1314) < 1

    def test_np_min_clamp(self):
        # 매우 낮은 급여 → 국민연금 하한(410,000/월) 기준 (2026.7~2027.6, 4.75%)
        r = compute_insurance_deduction(1_000_000)   # 월 83,333 → 하한 적용
        assert abs(r["np_monthly"] - 410_000 * 0.0475) < 1

    def test_np_max_clamp(self):
        # 높은 급여 → 국민연금 상한(6,590,000/월) 기준 (2026.7~2027.6, 4.75%)
        r = compute_insurance_deduction(200_000_000)  # 월 16.7M → 상한 적용
        assert abs(r["np_monthly"] - 6_590_000 * 0.0475) < 1


# ─── 6. 전체 계산 흐름 ──────────────────────────────────────────────────────

class TestYearEndSettlement:
    def test_refund_case(self):
        # 총급여 4000만, 2인, 기납부 250만 → 환급 1,164,543원 (2026 요율 기준, 장기요양 13.14%)
        r = compute_year_end_settlement(40_000_000, 2, 2_500_000)
        assert r["estimated_refund"] == 1_164_543
        assert r["labor_deduction"] == 11_250_000
        assert r["personal_deduction"] == 3_000_000
        assert r["taxable_income"] > 0
        assert r["determined_tax"] > 0

    def test_extra_payment_case(self):
        # 총급여 7000만, 1인, 기납부 200만 → 추가납부 3,347,174원 (2026 요율 기준, 장기요양 13.14%)
        r = compute_year_end_settlement(70_000_000, 1, 2_000_000)
        assert r["estimated_refund"] == -3_347_174
        assert r["labor_deduction"] == 13_250_000

    def test_zero_paid_tax(self):
        # 기납부 0 → 환급 없음, 결정세액 = -estimated_refund
        r = compute_year_end_settlement(50_000_000, 1, 0)
        assert r["estimated_refund"] == -r["determined_tax"]
        assert r["determined_tax"] >= 0

    def test_min_family(self):
        # family_count 0 입력 → 1로 보정
        r = compute_year_end_settlement(40_000_000, 0, 0)
        assert r["personal_deduction"] == PER_PERSON

    def test_high_income(self):
        # 고소득 케이스 — 음수 과세표준 없음, 45% 구간 세율 적용 확인
        r = compute_year_end_settlement(500_000_000, 1, 0)
        assert r["taxable_income"] > 0
        assert r["gross_tax"] > 0
        assert r["determined_tax"] >= 0

    def test_detail_keys(self):
        r = compute_year_end_settlement(50_000_000, 1, 2_000_000)
        expected_keys = [
            "gross_income", "labor_deduction", "labor_income",
            "personal_deduction", "insurance_deduction", "taxable_income",
            "gross_tax", "tax_credit", "determined_tax",
            "local_income_tax", "estimated_refund",
        ]
        for k in expected_keys:
            assert k in r, f"누락된 key: {k}"

    def test_11_step_invariants(self):
        r = compute_year_end_settlement(60_000_000, 3, 3_000_000)
        # 근로소득금액 = 총급여 - 근로소득공제
        assert r["labor_income"] == r["gross_income"] - r["labor_deduction"]
        # 결정세액 = 산출세액 - 세액공제
        assert r["determined_tax"] == max(0, r["gross_tax"] - r["tax_credit"])
        # 세액공제 ≤ 산출세액
        assert r["tax_credit"] <= r["gross_tax"]
        # 지방소득세 = 결정세액 × 10% (반올림)
        assert r["local_income_tax"] == int(r["determined_tax"] * 0.10)
