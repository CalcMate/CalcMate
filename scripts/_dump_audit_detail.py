# -*- coding: utf-8 -*-
"""4개 계산기의 article_content form 블록 + faq[2] 정밀 확인."""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

cfg = load_config(); db = get_db_adapter(cfg); repo = CalculatorRepository(db)
calcs = repo.get_all()

TARGETS = [
    ("weekly-holiday-allowance", "주휴수당"),
    ("unemployment-benefit", "실업급여"),
    ("four-insurances", "4대보험"),
    ("annual-leave-allowance", "연차수당"),
]

for slug, name in TARGETS:
    c = next((x for x in calcs if x.get("slug") == slug), None)
    art = c.get("article_content") or ""
    faq = json.loads(c.get("faq") or "[]")
    print(f"\n{'='*60}")
    print(f" [{name} / {slug}]")
    print(f"{'='*60}")

    # form 블록 추출
    m = re.search(r'<form[\s>].*?</form>', art, re.DOTALL)
    if m:
        print(f"  Form 블록 (repr):\n  {repr(m.group(0)[:400])}")
    else:
        print("  Form 없음")

    # faq[2] answer
    if len(faq) > 2:
        print(f"\n  faq[2] answer:\n  {repr(faq[2]['answer'][:300])}")

    # 코드 변수명 포함 faq answer
    for i, f in enumerate(faq):
        ans = f.get("answer", "")
        if re.search(r"공식은\s*['\"]", ans) or re.search(r'[a-z_]{4,}\s*[x×]\s*', ans):
            print(f"\n  faq[{i}] 공식/수식 포함:\n  {repr(ans[:200])}")
