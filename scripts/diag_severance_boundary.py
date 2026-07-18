# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")

cases = [
    ("0일",          0,   3_000_000),
    ("1일",          1,   3_000_000),
    ("364일",      364,   3_000_000),
    ("365일",      365,   3_000_000),
    ("366일",      366,   3_000_000),
    ("730일(2년)", 730,   3_000_000),
    ("3650일(10년)", 3650, 5_000_000),
]

print("="*72)
print(" 퇴직금 경계값 검증 — 계산기 vs 법령(근로자퇴직급여보장법 제8조)")
print(" 기준: 1년(365일) 미만 → 법적 지급 의무 없음(0원)")
print("="*72)
print(f"{'케이스':20} | {'계산기 결과':>14} | {'법령 기준':>14} | 판정")
print("-"*72)

issues = []
for label, days, wage in cases:
    # 현재 계산기 로직: total_days > 0 이면 계산, 아니면 0
    calc = wage * (days / 365) if days > 0 else 0
    # 법령: 1년(365일) 이상인 경우에만 지급
    legal = wage * (days / 365) if days >= 365 else 0
    ok = abs(calc - legal) < 1
    tag = "OK " if ok else "NG "
    legal_str = f"{int(legal):,}원" if not ok else ""
    note = f"(법령:{legal_str})" if legal_str else ""
    print(f"{label:20} | {int(calc):>14,} | {int(legal):>14,} | {tag} {note}")
    if not ok:
        issues.append((label, int(calc), int(legal)))

print()
print("="*72)
print("3건 정부 계산기 비교 (법령 공식 직접 계산):")
gov_cases = [
    ("1년 경계: 월임금 300만×365일", 3_000_000, 365),
    ("일반: 월임금 300만×730일",     3_000_000, 730),
    ("장기: 월임금 500만×3650일",    5_000_000, 3650),
]
for desc, wage, days in gov_cases:
    gov = wage * (days / 365)       # 법령: 일평균임금×30×(재직일수/365) = 월임금×(재직일수/365)
    calc = wage * (days / 365) if days > 0 else 0
    tag = "OK " if abs(calc - gov) < 1 else "NG "
    print(f"  {tag} {desc}: {int(calc):,}원 (정부기준 {int(gov):,}원)")

print()
if issues:
    print(f"[FAIL] {len(issues)}건 불일치:")
    for label, calc, legal in issues:
        print(f"  - {label}: 계산기={calc:,}원 / 법령기준={legal:,}원")
else:
    print("[PASS] 모든 경계값 일치")

print()
print("추가 검증 — 음수 평균임금:")
for wage in [-1_000_000, 0]:
    total_days = 365
    calc = wage * (total_days / 365) if total_days > 0 else 0
    print(f"  평균월임금 {wage:,}원, 재직 365일 → 계산기: {int(calc):,}원  ({'음수/0 결과 노출됨' if calc <= 0 else '정상'})")

print()
print("추가 검증 — 날짜 미입력(Invalid Date):")
import math
nan = float("nan")
total_days_nan = nan
severance_nan = wage * (total_days_nan / 365) if total_days_nan > 0 else 0
# NaN > 0 → False → severance = 0
print(f"  날짜 미입력 → total_days=NaN → severance_pay=0원, _detail=[재직일수:0일]")
print(f"  isFinite(0)=True → 결과카드 표시됨 (alert 없음)")
