# -*- coding: utf-8 -*-
"""SP-2 — 재생성된 3개 계산기 HTML forbidden_articles 재검증"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = ROOT / "data" / "workspace"

FORBIDDEN_MAP = {
    "severance-pay":           ["근로기준법 제34조"],
    "연말정산_환급액_계산기":  ["소득세법 제55조", "소득세법 제63조"],
    "육아휴직_급여_계산기":    ["고용보험법 제40조", "근로기준법 제74조"],
}

# 올바른 조문이 포함됐는지 확인 (positive check)
CORRECT_MAP = {
    "severance-pay":          "근로자퇴직급여보장법 제8조",
    "연말정산_환급액_계산기": "소득세법 제137조",
    "육아휴직_급여_계산기":   "고용보험법 제70조",
}

def norm(s): return re.sub(r"\s+", "", str(s or ""))

print("="*70)
print(" SP-2 재생성 HTML forbidden 재검증")
print("="*70)

all_ok = True
for slug, forbidden_list in FORBIDDEN_MAP.items():
    html_file = WORKSPACE / slug / "index.html"
    if not html_file.exists():
        print(f"\n[MISS] {slug}/index.html — 파일 없음")
        all_ok = False
        continue

    content = html_file.read_text(encoding="utf-8", errors="ignore")
    content_norm = norm(content)

    # forbidden 검사 (제거됐어야 함)
    found_forbidden = [f for f in forbidden_list if norm(f) in content_norm]

    # correct 검사 (삽입됐어야 함)
    correct = CORRECT_MAP[slug]
    has_correct = norm(correct) in content_norm

    if found_forbidden:
        print(f"\n[NG] {slug}")
        for f in found_forbidden:
            print(f"  forbidden 잔존: {f}")
        all_ok = False
    elif not has_correct:
        print(f"\n[WARN] {slug}")
        print(f"  올바른 조문 '{correct}' 미발견 (FAQ가 렌더링 안 됐을 수 있음)")
        all_ok = False
    else:
        print(f"\n[OK] {slug}")
        print(f"  forbidden 없음, 올바른 조문 확인: {correct}")

print("\n" + "="*70)
print("결과:", "전체 OK" if all_ok else "일부 NG — 위 항목 확인")
