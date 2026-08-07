# -*- coding: utf-8 -*-
"""각 계산기 article_content form 블록 전후 컨텍스트 확인."""
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
    c   = next((x for x in calcs if x.get("slug") == slug), None)
    art = c.get("article_content") or ""
    m   = re.search(r'<form[\s>].*?</form>', art, re.DOTALL)
    if not m:
        print(f"[{name}] form 없음\n"); continue

    start = m.start()
    end   = m.end()
    ctx   = art[max(0, start-200):end+300]
    print(f"\n{'='*60}")
    print(f" [{name}] form 전후 컨텍스트 repr")
    print(f"{'='*60}")
    print(repr(ctx))
