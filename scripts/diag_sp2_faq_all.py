# -*- coding: utf-8 -*-
"""SP-2 - 연말정산·육아휴직 DB faq 전문 출력"""
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

TARGETS = ["연말정산_환급액_계산기", "육아휴직_급여_계산기"]
for slug in TARGETS:
    sp = next((c for c in calcs if c.get("slug") == slug), None)
    if not sp:
        print(f"[없음] {slug}")
        continue
    print(f"\n{'='*60}")
    print(f" [{slug}] faq 전문")
    print(f"{'='*60}")
    faq_raw = sp.get("faq") or ""
    try:
        faq = json.loads(faq_raw) if isinstance(faq_raw, str) else faq_raw
        for i, item in enumerate(faq, 1):
            q = item.get("question") or item.get("q") or ""
            a = item.get("answer") or item.get("a") or ""
            print(f"\n  [{i}] Q: {q}")
            print(f"      A: {a}")
    except Exception:
        print(faq_raw)
