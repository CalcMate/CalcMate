# -*- coding: utf-8 -*-
"""SP-2 재검증 — forbidden 텍스트 정확한 위치 찾기"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = ROOT / "data" / "workspace"

TARGETS = {
    "severance-pay":        ["근로기준법 제34조"],
    "육아휴직_급여_계산기": ["고용보험법 제40조", "근로기준법 제74조"],
}

for slug, needles in TARGETS.items():
    html_file = WORKSPACE / slug / "index.html"
    if not html_file.exists():
        print(f"[없음] {slug}/index.html")
        continue

    lines = html_file.read_text(encoding="utf-8", errors="ignore").splitlines()
    print(f"\n{'='*60}")
    print(f" {slug}/index.html — forbidden 위치")
    print(f"{'='*60}")

    for needle in needles:
        norm_needle = re.sub(r"\s+", "", needle)
        found = False
        for i, line in enumerate(lines, 1):
            if norm_needle in re.sub(r"\s+", "", line):
                print(f"  L{i}: {line.strip()[:120]}")
                found = True
        if not found:
            print(f"  [{needle}] — 없음")
