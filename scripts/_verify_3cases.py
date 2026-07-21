# -*- coding: utf-8 -*-
"""법령 직접 수동 계산 vs Python mirror — 3케이스 비교."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
from modules.income_tax_calculator import (
    compute_labor_income_deduction,
    compute_income_tax,
    compute_earned_tax_credit_limit,
    compute_earned_tax_credit,
    compute_insurance_deduction,
    compute_year_end_settlement,
)

# 법령 수동 계산 (소득세법 직접 적용, 원 단위)
def manual_compute(total_salary):
    # ② 근로소득공제 (소득세법 제47조)
    s = total_salary
    if s <= 5_000_000:
        ld = int(s * 0.70)
    elif s <= 15_000_000:
        ld = int(3_500_000 + (s - 5_000_000) * 0.40)
    elif s <= 45_000_000:
        ld = int(7_500_000 + (s - 15_000_000) * 0.15)
    elif s <= 100_000_000:
        ld = int(12_000_000 + (s - 45_000_000) * 0.05)
    else:
        ld = int(14_750_000 + (s - 100_000_000) * 0.02)
    ld = min(ld, 20_000_000)

    # ③ 근로소득금액
    li = s - ld

    # ④ 인적공제 1인
    pd = 1_500_000

    # ⑤ 4대보험 (월 → 연, 각 항목 별도 계산, round 없이 float 합산 후 int)
    m = s / 12
    np_base = min(max(m, 390_000), 6_170_000)
    np_m  = np_base  * 0.045
    hi_m  = m        * 0.03545
    ltc_m = hi_m     * 0.1296
    ei_m  = m        * 0.009
    ins = int((np_m + hi_m + ltc_m + ei_m) * 12)

    # ⑥ 과세표준
    tax_base = max(0, li - pd - ins)

    # ⑦ 산출세액 (소득세법 제55조)
    t = int(tax_base)
    if t <= 14_000_000:
        gt = max(0, int(t * 0.06 - 0))
    elif t <= 50_000_000:
        gt = max(0, int(t * 0.15 - 1_260_000))
    elif t <= 88_000_000:
        gt = max(0, int(t * 0.24 - 5_760_000))
    elif t <= 150_000_000:
        gt = max(0, int(t * 0.35 - 15_440_000))
    elif t <= 300_000_000:
        gt = max(0, int(t * 0.38 - 19_940_000))
    elif t <= 500_000_000:
        gt = max(0, int(t * 0.40 - 25_940_000))
    elif t <= 1_000_000_000:
        gt = max(0, int(t * 0.42 - 35_940_000))
    else:
        gt = max(0, int(t * 0.45 - 65_940_000))

    # ⑧ 근로소득세액공제 (소득세법 제59조)
    if gt <= 1_300_000:
        raw_credit = int(gt * 0.55)
    else:
        raw_credit = int(715_000 + (gt - 1_300_000) * 0.30)

    if s <= 33_000_000:
        cl = 740_000
    elif s <= 70_000_000:
        cl = int(max(740_000 - (s - 33_000_000) * 0.008, 660_000))
    elif s <= 120_000_000:
        cl = int(max(660_000 - (s - 70_000_000) * 0.5, 500_000))
    else:
        cl = int(max(500_000 - (s - 120_000_000) * 0.5, 200_000))

    tc = min(raw_credit, cl)

    # ⑨ 결정세액
    dt = max(0, gt - tc)

    return {
        "labor_deduction": ld, "labor_income": li,
        "personal_deduction": pd, "insurance_deduction": ins,
        "taxable_income": int(tax_base), "gross_tax": gt,
        "tax_credit": tc, "determined_tax": dt,
    }

CASES = [30_000_000, 50_000_000, 100_000_000]
LABELS = {
    "labor_deduction":    "②근로소득공제",
    "labor_income":       "③근로소득금액",
    "personal_deduction": "④인적공제(1인)",
    "insurance_deduction":"⑤4대보험공제",
    "taxable_income":     "⑥과세표준",
    "gross_tax":          "⑦산출세액",
    "tax_credit":         "⑧근로소득세액공제",
    "determined_tax":     "⑨결정세액",
}

print("=" * 78)
print("비교 조건: 1인가구, 추가 세액공제 없음, 기납부 0")
print("기준: 소득세법 제47조·제55조·제59조 (2025년 귀속)")
print("=" * 78)

for ts in CASES:
    man = manual_compute(ts)
    prog = compute_year_end_settlement(ts, 1, 0)

    print(f"\n▶ 총급여 {ts:,}원")
    print(f"  {'항목':<16} {'법령 직접계산':>14} {'프로그램':>14} {'오차':>8}")
    print(f"  {'-'*16} {'-'*14} {'-'*14} {'-'*8}")
    for k, label in LABELS.items():
        mv = man[k]
        pv = prog[k]
        diff = pv - mv
        mark = "✓" if diff == 0 else f"Δ{diff:+,}"
        print(f"  {label:<16} {mv:>14,} {pv:>14,} {mark:>8}")

print("\n" + "=" * 78)
print("오차 요약")
print("=" * 78)
all_zero = True
for ts in CASES:
    man = manual_compute(ts)
    prog = compute_year_end_settlement(ts, 1, 0)
    diffs = {k: prog[k] - man[k] for k in LABELS}
    nonzero = {k: v for k, v in diffs.items() if v != 0}
    if nonzero:
        all_zero = False
        print(f"  총급여 {ts:,}: 오차 있음 → {nonzero}")
    else:
        print(f"  총급여 {ts:,}: 오차 0원 ✓")

print()
if all_zero:
    print("✅ 3케이스 전체 오차 0원 — 소득세법 법령 직접 계산 = 프로그램 결과")
else:
    print("❌ 오차 발생 케이스 있음")
print("=" * 78)
