# -*- coding: utf-8 -*-
"""실업급여 reference cases 계산 — 함수 실행 결과로 예시값 확정"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from tests.test_unemployment_benefit_compute import compute_ub, DAILY_MAX, DAILY_MIN

cases = [
    ("A", 35,  24, 100_000, "35세/24개월/일급100,000 [under50 12~36]"),
    ("B", 45,  60, 110_000, "45세/60개월/일급110,000 [under50 60~120]"),
    ("C", 55, 120, 130_000, "55세/120개월/일급130,000 [age50p 120+, 상한]"),
    ("D", 40,  36,  80_000, "40세/36개월/일급80,000 [under50 36~60, 하한]"),
    ("E", 35,   6, 100_000, "35세/6개월(경계)/일급100,000 [수급 최소]"),
    ("F", 49,  24, 100_000, "49세/24개월/일급100,000 [49세 under50]"),
    ("G", 50,  24, 100_000, "50세/24개월/일급100,000 [50세 age50p]"),
    ("H", 50,  60, 110_000, "50세/60개월/일급110,000 [age50p 60~120]"),
    ("I", 49, 120, 100_000, "49세/120개월/일급100,000 [under50 최대 240일]"),
    ("J", 50, 120, 100_000, "50세/120개월/일급100,000 [age50p 최대 270일]"),
]

print(f"DAILY_MAX={DAILY_MAX:,}원  DAILY_MIN={DAILY_MIN:,}원")
print()
for key, age, months, wage, desc in cases:
    r = compute_ub(wage, age, months)
    raw = wage * 0.6
    clamp = "상한" if raw > DAILY_MAX else ("하한" if raw < DAILY_MIN else "없음")
    print(f"[{key}] {desc}")
    print(f"     입력: 일급={wage:,}원  나이={age}세  가입={months}개월")
    print(f"     raw={raw:,.0f}원  클램프={clamp}  daily={r['daily_benefit']:,.0f}원  days={r['benefit_days']}일  total={r['total_benefit']:,.0f}원")
    if r.get("notices"):
        for n in r["notices"]:
            print(f"     notice: {n[:60]}")
    print()
