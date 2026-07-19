# -*- coding: utf-8 -*-
"""SP-2 - 계산기 HTML workspace 7개 전수 forbidden_articles 스캔"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = ROOT / "data" / "workspace"

# forbidden_articles per slug (legal_basis.draft.yaml 기준)
FORBIDDEN_MAP = {
    "severance-pay":           ["근로기준법 제34조"],
    "육아휴직_급여_계산기":     ["고용보험법 제40조", "근로기준법 제74조"],
    "연말정산_환급액_계산기":   ["소득세법 제55조", "소득세법 제63조"],
    "weekly-holiday-allowance": [],
    "annual-leave-allowance":   [],
    "unemployment-benefit":     [],
    "four-insurances":          [],
}

def norm(s): return re.sub(r"\s+", "", str(s or ""))

print("="*72)
print(" 계산기 HTML workspace 전수 forbidden_articles 스캔")
print(" (data/workspace/{slug}/index.html — G8 사각지대)")
print("="*72)

total_hits = 0
for slug, forbidden_list in FORBIDDEN_MAP.items():
    calc_dir = WORKSPACE / slug
    html_file = calc_dir / "index.html"
    if not html_file.exists():
        print(f"\n[SKIP] {slug} — index.html 없음")
        continue

    content = html_file.read_text(encoding="utf-8", errors="ignore")
    content_norm = norm(content)

    # slug별 forbidden 검사
    slug_hits = [f for f in forbidden_list if norm(f) in content_norm]

    # 추가: 모든 forbidden 패턴 (다른 계산기 것도 혼입됐는지 교차 확인)
    from docs_load import ALL_FORBIDDEN_PATTERNS  # 아래 로컬 정의
    cross_hits = []
    for fa_slug, fa_list in FORBIDDEN_MAP.items():
        if fa_slug == slug:
            continue
        for f in fa_list:
            if norm(f) in content_norm:
                cross_hits.append(f"{f} (본래 {fa_slug} forbidden)")

    if slug_hits or cross_hits:
        total_hits += 1
        print(f"\n[NG] {slug}")
        for h in slug_hits:
            # 위치 찾기
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                if norm(h) in norm(line):
                    print(f"       L{i}: ...{line.strip()[:80]}...")
            print(f"       ↑ forbidden: {h}")
        for h in cross_hits:
            print(f"       교차 오염: {h}")
    else:
        print(f"\n[OK] {slug} — forbidden 없음")

print("\n" + "="*72)
print(f"합계: {total_hits}개 계산기 HTML에서 forbidden 발견")
