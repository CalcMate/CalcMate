# -*- coding: utf-8 -*-
"""04번/07번 본문 실제 텍스트 발췌"""
import sys, re
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
from modules.publish_quality import _plain_text

arts = BASE / "data" / "phase5-c" / "articles"

# ── 04번: 3.545%, 12.96% 맥락 발췌 (긴 단위로)
f04 = sorted(arts.glob("04_*.html"))[0]
txt04 = _plain_text(f04.read_text(encoding="utf-8"))

print("=== 04번 전체 본문 (관련 부분) ===")
for para in re.split(r'\n{2,}', txt04):
    para = para.strip()
    if "3.545" in para or "12.96" in para or "보험료율" in para or "건강보험" in para:
        print(f"  {para[:200]}")
        print()

# ── 07번: 계산 방법 / 통상임금 관련 발췌
f07 = sorted(arts.glob("07_*.html"))[0]
h07 = f07.read_text(encoding="utf-8")
txt07 = _plain_text(h07)

print("=== 07번 전체 본문 ===")
print(txt07[:2500])

print("\n=== 07번 FAQ만 ===")
faq_m = re.search(r'<h2[^>]*>\s*FAQ\s*</h2>(.*)', h07, re.I|re.DOTALL)
if faq_m:
    faq_txt = _plain_text(faq_m.group(0))
    print(faq_txt[:1500])
