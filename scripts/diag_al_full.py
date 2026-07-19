# -*- coding: utf-8 -*-
"""연차수당 계산기 진단 스크립트."""
import sys
sys.stdout.reconfigure(encoding="utf-8")


def annual_leave_days(years: int) -> int:
    """근속연수(정수)에 따른 연차 발생 일수 (1년 이상, 근로기준법 제60조)."""
    if years < 1:
        return 0
    base = 15
    add = (years - 1) // 2
    return min(base + add, 25)


print("=" * 60)
print(" 연차 발생 일수 전체 대조표 (근로기준법 제60조)")
print("=" * 60)
print()
print("1년 미만: 1개월 개근당 1일 (최대 11일)")
print("  0개월: 발생 없음")
print("  1개월 개근: 1일")
print("  11개월 개근: 11일")
print("  12개월 = 1년 이상 규칙 전환")
print()

header = f"{'근속':>5} {'연차':>5} {'가산':>5}  비고"
print(header)
print("-" * 45)

prev = None
for y in range(1, 26):
    d = annual_leave_days(y)
    add_n = (y - 1) // 2
    note = ""
    if y == 1:
        note = "기준 15일"
    elif y == 3:
        note = "최초 가산 (+1)"
    elif d == 25 and prev == 25:
        note = "상한 유지"
    elif d == 25 and prev == 24:
        note = "상한 도달"
    elif prev is not None and d > prev:
        note = "+1일 가산"
    print(f"{y}년   {d}일   {add_n}회  {note}")
    prev = d

print()
print("=" * 60)
print(" 특별 주목 경계 (20년~23년)")
print("=" * 60)
for y in [20, 21, 22, 23]:
    print(f"  {y}년: {annual_leave_days(y)}일")

print()
print("=" * 60)
print(" 3년 단위 가산 경계 3점 세트")
print("=" * 60)
for y_center in [3, 6, 9, 12, 15, 18, 21]:
    for y in [y_center - 1, y_center, y_center + 1]:
        if y < 1:
            continue
        mark = " <-- 가산" if annual_leave_days(y) != annual_leave_days(y - 1 if y > 1 else 1) and y > 1 else ""
        print(f"  {y}년: {annual_leave_days(y)}일{mark}")
    print()

print("=" * 60)
print(" 정부 기준 비교 케이스 3건")
print("=" * 60)
print("1) 1년 미만 (개월 단위 최대 11일)")
print("   계산기: daily_wage * unused_days (사용자 직접 입력)")
print("   정부 기준: 1개월 개근 1일 발생 (근로기준법 제60조제2항)")

y2 = 5
dw = 100_000
print(f"2) {y2}년차: 연차 {annual_leave_days(y2)}일")
print(f"   일급 {dw:,}원 x {annual_leave_days(y2)}일 = {dw * annual_leave_days(y2):,}원")

y3 = 21
print(f"3) {y3}년차: 연차 {annual_leave_days(y3)}일 (상한)")
print(f"   일급 {dw:,}원 x {annual_leave_days(y3)}일 = {dw * annual_leave_days(y3):,}원")

print()
print("=" * 60)
print(" 계산 공식 검증 (formula: daily_wage * unused_days)")
print("=" * 60)

cases = [
    (100_000, 5, 500_000, "faq[2] 예시"),
    (80_000, 4, 320_000, "article 예시1"),
    (120_000, 3, 360_000, "article 예시2"),
    (0, 5, 0, "일급=0 [AL-2 입력검증 없음]"),
    (100_000, 0, 0, "미사용=0 [AL-2 입력검증 없음]"),
    (-100_000, 5, -500_000, "음수 일급 -> 음수 결과 [AL-2 Critical]"),
    (100_000, 30, 3_000_000, "미사용 30일 -> 상한 초과 경고 없음"),
]

for dw2, ud, expected, note in cases:
    result = dw2 * ud
    ok = "OK" if result == expected else "NG"
    issues = []
    if dw2 <= 0:
        issues.append("null 미처리")
    if ud > 25:
        issues.append("법적 상한 25일 초과 경고 없음")
    if dw2 < 0:
        issues.append("음수 결과 표시됨")
    issue_str = " => " + ", ".join(issues) if issues else ""
    print(f"  {dw2:>10,} x {ud:>3}일 = {result:>12,}원  [{ok}] {note}{issue_str}")

print()
print("=" * 60)
print(" 법령 근거 진단")
print("=" * 60)
print("legal_basis.yaml writer_note 요구사항:")
print("  [1] 근로기준법 제60조 언급")
print("  [2] 제61조 연차 사용 촉진제도 예외 언급")
print()
print("현재 상태:")
print("  [1] faq[4] 근로기준법 제60조 언급: OK")
print("  [2] 제61조 언급: NOT FOUND -> VIOLATION")
print("      reviewer_expectation 위반")
print()
print("faq[3] 통상임금 오류:")
print('  현재: "연차수당은 기본 일급만 기준으로 하므로"')
print("  정확: 연차수당 = 통상임금 기준 (근로기준법 제2조제1항제5호, 시행령 제6조)")
print("        통상임금 = 기본급 + 고정수당 (직책수당, 가족수당 中 전원지급분 등)")
print("  영향: 사용자가 고정수당을 제외하고 계산 -> 실제 받아야 할 수당보다 과소")
print()
print("faq[1] 퇴직 후 미사용 연차 오류:")
print('  현재: "근로계약이 해지된 후에도 미사용 연차가 있을 경우 지급되지 않을 수 있습니다"')
print("  정확: 퇴직 시 미사용 연차수당은 사용자가 의무 지급 (근로기준법 제60조제5항)")
print("        단, 제61조 연차 사용 촉진 적법 시행 시에만 면제 가능")
print("  영향: 사용자가 수당 청구 포기 가능성")
