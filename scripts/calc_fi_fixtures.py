# -*- coding: utf-8 -*-
"""Phase 2 이중 검증용 기준값 계산 (수기 합산 금지)"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

NP_RATE, NP_MIN, NP_MAX = 0.045, 390_000, 6_170_000
HI_RATE, LTC_RATE, EI_RATE = 0.03545, 0.1296, 0.009

def compute_fi(salary):
    np_base = min(max(salary, NP_MIN), NP_MAX)
    np  = np_base * NP_RATE
    hi  = salary * HI_RATE
    ltc = hi * LTC_RATE
    ei  = salary * EI_RATE
    tot = np + hi + ltc + ei
    return {"np": np, "hi": hi, "ltc": ltc, "ei": ei, "total": tot}

for s in [3_000_000]:
    r = compute_fi(s)
    np_r  = round(r["np"])
    hi_r  = round(r["hi"])
    ltc_r = round(r["ltc"])
    ei_r  = round(r["ei"])
    tot_r = round(r["total"])
    sum_r = np_r + hi_r + ltc_r + ei_r

    print(f"=== {s:,}원 기준 ===")
    print(f"  국민연금(NP):   raw={r['np']:.4f}  round={np_r:,}원")
    print(f"  건강보험(HI):   raw={r['hi']:.4f}  round={hi_r:,}원")
    print(f"  장기요양(LTC):  raw={r['ltc']:.4f}  round={ltc_r:,}원")
    print(f"  고용보험(EI):   raw={r['ei']:.4f}  round={ei_r:,}원")
    print(f"  ─────────────────────────────────────")
    print(f"  개별합(sum_r):  {sum_r:,}원")
    print(f"  합계(total):   raw={r['total']:.4f}  round={tot_r:,}원")
    print()

    # 이중 검증
    assert tot_r == sum_r or abs(tot_r - sum_r) <= 1, f"total({tot_r}) != sum({sum_r})"
    print("[검증] round(total) == sum(round(개별)) ±1원 이내: OK")
