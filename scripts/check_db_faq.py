# -*- coding: utf-8 -*-
"""DB faq 현재 상태 확인"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

cfg = load_config()
db = get_db_adapter(cfg)
calc_repo = CalculatorRepository(db)
calcs = calc_repo.get_all()

TARGETS = ["severance-pay", "육아휴직_급여_계산기"]
KEYWORDS = ["34조", "74조", "40조", "137조", "70조", "8조"]

for slug in TARGETS:
    calc = next((c for c in calcs if c.get("slug") == slug), None)
    if not calc:
        print(f"[없음] {slug}")
        continue
    faq_raw = calc.get("faq") or "[]"
    faq = json.loads(faq_raw) if isinstance(faq_raw, str) else faq_raw
    print(f"\n{'='*60}")
    print(f" {slug} DB faq (현재)")
    print(f"{'='*60}")
    for i, item in enumerate(faq, 1):
        q = item.get("question") or item.get("q") or ""
        a = item.get("answer") or item.get("a") or ""
        hits = [k for k in KEYWORDS if k in a]
        print(f"  [{i}] Q: {q}")
        print(f"       A: {a[:120]}")
        if hits:
            print(f"       *** 발견 조문: {hits} ***")

# 육아휴직 notes 필드도 확인
print(f"\n{'='*60}")
print(" 육아휴직_급여_계산기 — 모든 필드 중 74조/40조 위치")
print(f"{'='*60}")
calc = next((c for c in calcs if c.get("slug") == "육아휴직_급여_계산기"), None)
if calc:
    for k, v in calc.items():
        if v and ("74조" in str(v) or "40조" in str(v)):
            print(f"  필드 '{k}': {str(v)[:200]}")
