# -*- coding: utf-8 -*-
"""SP-6 수정 결과 검증"""
import sys, re
sys.stdout.reconfigure(encoding="utf-8")

html = open("data/workspace/severance-pay/index.html", encoding="utf-8").read()

def norm(s): return re.sub(r"\s+", "", s)

ERROR_PATTERNS = [
    "초과근무수당이나상여금은포함하지않아야",
    "기본급과법정수당만포함하여계산해야",
    "상여금은포함하지않",
]
CORRECT_PATTERNS = [
    "연장",
    "야간",
    "휴일",
    "상여금",
    "근로기준법제2조",
    "시행령제2조",
]

print("[오류 문구 제거 확인]")
all_ok = True
for e in ERROR_PATTERNS:
    found = e in norm(html)
    tag = "NG" if found else "OK"
    if found:
        all_ok = False
    print(f"  [{tag}] {e}")

print("\n[올바른 내용 포함 확인]")
for c in CORRECT_PATTERNS:
    found = norm(c) in norm(html)
    tag = "OK" if found else "MISS"
    if not found:
        all_ok = False
    print(f"  [{tag}] {c}")

print("\n결과:", "전체 OK" if all_ok else "일부 NG")
