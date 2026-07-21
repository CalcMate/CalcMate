# -*- coding: utf-8 -*-
"""
modules/income_tax_calculator.py — 연말정산 계산 엔진 Python mirror (v1)

계산 흐름 (11단계):
①총급여 → ②근로소득공제(제47조) → ③근로소득금액 → ④인적공제(제50조)
→ ⑤4대보험공제 → ⑥과세표준 → ⑦산출세액(제55조)
→ ⑧근로소득세액공제(제59조) → ⑨결정세액 → ⑩지방소득세 → ⑪환급/추가납부

v1 제외(v1.1 이월): 자녀세액공제, 특별세액공제, 표준세액공제, 의료비/교육비/기부금,
                    신용카드, 주택자금 등 — 소득세법 제59조의2 이하 항목
"""

from modules.registry_loader import load_registry


def _get_yt_reg() -> dict:
    return load_registry().get("연말정산_환급액_계산기", {})


def compute_labor_income_deduction(total_salary: int) -> int:
    """소득세법 제47조 근로소득공제 (2025년 귀속). 한도 2,000만원."""
    reg = _get_yt_reg().get("labor_deduction_table", {})
    brackets = reg.get("brackets") or []
    max_ded = int(reg.get("max_deduction", 20_000_000))
    if not brackets:
        brackets = [
            {"limit": 5_000_000,   "rate": 0.70, "base": 0},
            {"limit": 15_000_000,  "rate": 0.40, "base": 3_500_000},
            {"limit": 45_000_000,  "rate": 0.15, "base": 7_500_000},
            {"limit": 100_000_000, "rate": 0.05, "base": 12_000_000},
            {"limit": None,        "rate": 0.02, "base": 14_750_000},
        ]
        max_ded = 20_000_000
    prev_limit = 0
    for b in brackets:
        limit = b.get("limit")
        if limit is None or total_salary <= limit:
            deduction = b["base"] + (total_salary - prev_limit) * b["rate"]
            return int(min(deduction, max_ded))
        prev_limit = limit
    return max_ded


def compute_income_tax(taxable_income: int) -> int:
    """소득세법 제55조 누진세율 산출세액 (2025년 귀속)."""
    if taxable_income <= 0:
        return 0
    reg = _get_yt_reg().get("income_tax_brackets", {})
    brackets = reg.get("brackets") or []
    if not brackets:
        brackets = [
            {"limit": 14_000_000,   "rate": 0.06, "deduction": 0},
            {"limit": 50_000_000,   "rate": 0.15, "deduction": 1_260_000},
            {"limit": 88_000_000,   "rate": 0.24, "deduction": 5_760_000},
            {"limit": 150_000_000,  "rate": 0.35, "deduction": 15_440_000},
            {"limit": 300_000_000,  "rate": 0.38, "deduction": 19_940_000},
            {"limit": 500_000_000,  "rate": 0.40, "deduction": 25_940_000},
            {"limit": 1_000_000_000,"rate": 0.42, "deduction": 35_940_000},
            {"limit": None,         "rate": 0.45, "deduction": 65_940_000},
        ]
    for b in brackets:
        limit = b.get("limit")
        if limit is None or taxable_income <= limit:
            return max(0, int(taxable_income * b["rate"] - b["deduction"]))
    return max(0, int(taxable_income * 0.45 - 65_940_000))


def compute_earned_tax_credit_limit(total_salary: int) -> int:
    """소득세법 제59조제3항 근로소득세액공제 한도."""
    reg = _get_yt_reg().get("tax_credit_limits", {})
    limits = reg.get("limits") or []
    if not limits:
        if total_salary <= 33_000_000:
            return 740_000
        elif total_salary <= 70_000_000:
            return int(max(740_000 - (total_salary - 33_000_000) * 0.008, 660_000))
        elif total_salary <= 120_000_000:
            return int(max(660_000 - (total_salary - 70_000_000) * 0.5, 500_000))
        else:
            return int(max(500_000 - (total_salary - 120_000_000) * 0.5, 200_000))
    prev_max = 0
    for seg in limits:
        smax = seg.get("salary_max")
        if smax is None or total_salary <= smax:
            if seg.get("fixed") is not None:
                return int(seg["fixed"])
            val = seg["base"] - (total_salary - seg["ref"]) * seg["reduce_rate"]
            return int(max(val, seg["floor"]))
        prev_max = smax
    return 200_000


def compute_earned_tax_credit(gross_tax: int) -> int:
    """소득세법 제59조제1항 근로소득세액공제액."""
    reg = _get_yt_reg().get("tax_credit_limits", {})
    threshold  = int(reg.get("credit_threshold", 1_300_000))
    rate_low   = float(reg.get("credit_rate_low", 0.55))
    rate_high  = float(reg.get("credit_rate_high", 0.30))
    base_high  = int(reg.get("credit_base_high", 715_000))
    if gross_tax <= threshold:
        return int(gross_tax * rate_low)
    return int(base_high + (gross_tax - threshold) * rate_high)


def compute_insurance_deduction(total_salary: int) -> dict:
    """4대보험 공제 연간 합계 — four-insurances 요율 상수 재사용."""
    ir = load_registry().get("four-insurances", {}).get("insurance_rates", {})
    NP_RATE  = float(ir.get("np_rate",  0.045))
    NP_MIN   = int(ir.get("np_min",   390_000))
    NP_MAX   = int(ir.get("np_max",   6_170_000))
    HI_RATE  = float(ir.get("hi_rate",  0.03545))
    LTC_RATE = float(ir.get("ltc_rate", 0.1296))
    EI_RATE  = float(ir.get("ei_rate",  0.009))
    monthly  = total_salary / 12
    np_base  = min(max(monthly, NP_MIN), NP_MAX)
    np_m     = np_base * NP_RATE
    hi_m     = monthly * HI_RATE
    ltc_m    = hi_m * LTC_RATE
    ei_m     = monthly * EI_RATE
    annual   = (np_m + hi_m + ltc_m + ei_m) * 12
    return {
        "np_monthly": np_m,
        "hi_monthly": hi_m,
        "ltc_monthly": ltc_m,
        "ei_monthly": ei_m,
        "annual_total": annual,
    }


def compute_year_end_settlement(
    total_salary: int,
    family_count: int,
    paid_tax: int,
) -> dict:
    """연말정산 전체 계산 (v1). 11단계 _detail 반환."""
    per_person = int(
        _get_yt_reg().get("personal_deduction", {}).get("per_person", 1_500_000)
    )
    # ①총급여
    gross = int(total_salary)
    # ②근로소득공제
    labor_deduction = compute_labor_income_deduction(gross)
    # ③근로소득금액
    labor_income = gross - labor_deduction
    # ④인적공제
    n = max(1, int(family_count))
    personal_deduction = min(n * per_person, labor_income)
    # ⑤4대보험공제
    ins = compute_insurance_deduction(gross)
    insurance_deduction = ins["annual_total"]
    # ⑥과세표준
    taxable_income = max(0.0, labor_income - personal_deduction - insurance_deduction)
    # ⑦산출세액
    gross_tax = compute_income_tax(int(taxable_income))
    # ⑧세액공제
    raw_credit    = compute_earned_tax_credit(gross_tax)
    credit_limit  = compute_earned_tax_credit_limit(gross)
    tax_credit    = min(raw_credit, credit_limit)
    # ⑨결정세액
    determined_tax = max(0, gross_tax - tax_credit)
    # ⑩지방소득세
    local_income_tax = int(determined_tax * 0.10)
    # ⑪환급/추가납부 (양수=환급, 음수=추가납부)
    estimated_refund = int(paid_tax) - determined_tax
    return {
        "gross_income":       gross,
        "labor_deduction":    labor_deduction,
        "labor_income":       labor_income,
        "personal_deduction": int(personal_deduction),
        "insurance_deduction":int(insurance_deduction),
        "taxable_income":     int(taxable_income),
        "gross_tax":          gross_tax,
        "tax_credit":         tax_credit,
        "determined_tax":     determined_tax,
        "local_income_tax":   local_income_tax,
        "estimated_refund":   estimated_refund,
    }
