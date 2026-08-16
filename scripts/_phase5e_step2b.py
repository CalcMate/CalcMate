# -*- coding: utf-8 -*-
"""Phase 5-E STEP 2 보완: G-STYLE+ 원인 + 본문 발췌"""
import sys, re
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from modules.publish_quality import _plain_text
from modules.content_integrity import (
    check_g_style_plus, run_integrity_gates, _ALL_GATES
)

arts = BASE / "data" / "phase5-c" / "articles"

# ── 05번 G-STYLE+ 원인 ──────────────────────────────────────────────────
f05 = sorted(arts.glob("05_*.html"))[0]
h05 = f05.read_text(encoding="utf-8")

style_fails = check_g_style_plus(h05)
print("=== 05번 G-STYLE+ 상세 ===")
if style_fails:
    for f in style_fails:
        print(f"  grade={f['grade']}: {f['detail']}")
else:
    print("  (실패 없음)")

p, failed = run_integrity_gates(h05, slug="annual-leave-allowance", intent="howto")
print(f"All gates: {sorted(_ALL_GATES)}")
print(f"Passed:    {p}")
for f in failed:
    print(f"  Failed: {f['gate']} ({f['grade']}) — {f['detail'][:80]}")

# ── 04번: 3.545% 본문 발췌 ────────────────────────────────────────────────
f04 = sorted(arts.glob("04_*.html"))[0]
h04 = f04.read_text(encoding="utf-8")
txt04 = _plain_text(h04)

print("\n=== 04번: 3.545%/12.96% 본문 발췌 ===")
for line in txt04.split("\n"):
    if "3.545" in line or "12.96" in line:
        print(f"  {line.strip()[:120]}")

# ── 07번: 계산 방법 섹션 발췌 ────────────────────────────────────────────
f07 = sorted(arts.glob("07_*.html"))[0]
h07 = f07.read_text(encoding="utf-8")
txt07 = _plain_text(h07)

print("\n=== 07번: 계산 방법 섹션 발췌 ===")
in_section = False
for line in txt07.split("\n"):
    if "계산 방법" in line:
        in_section = True
    if in_section and ("FAQ" in line or "지급 대상" in line or "근로시간" in line):
        break
    if in_section and line.strip():
        print(f"  {line.strip()[:120]}")

# ── 07번: '통상임금' 키워드 등장 확인 ───────────────────────────────────
print("\n=== 07번: '통상임금 80%' 맥락 ===")
for line in txt07.split("\n"):
    if "통상임금" in line and line.strip():
        print(f"  {line.strip()[:120]}")

# ── 10번: '14일 이내' 본문 발췌 ──────────────────────────────────────────
f10 = sorted(arts.glob("10_*.html"))[0]
h10 = f10.read_text(encoding="utf-8")
txt10 = _plain_text(h10)

print("\n=== 10번: '14일 이내' 발췌 ===")
for line in txt10.split("\n"):
    if "14일" in line and line.strip():
        print(f"  {line.strip()[:120]}")

# ── 07번 category_categories.yaml 키 부재 확인 ──────────────────────────
import yaml
cat_yaml = BASE / "config" / "calculator_categories.yaml"
cat_map = yaml.safe_load(cat_yaml.read_text(encoding="utf-8")) or {}
print("\n=== calculator_categories.yaml 현재 키 목록 ===")
for k in sorted(cat_map.keys()):
    print(f"  {k}: {cat_map[k]}")
