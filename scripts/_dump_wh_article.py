# -*- coding: utf-8 -*-
"""주휴수당 article_content 전체 + 공식 패턴 위치 확인."""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

cfg = load_config(); db = get_db_adapter(cfg); repo = CalculatorRepository(db)
calcs = repo.get_all()
wh = next(c for c in calcs if c.get("slug") == "weekly-holiday-allowance")
art = wh["article_content"]

print("=== 공식 패턴 검색 ===")
for m in re.finditer(r"공식은\s*['\"]", art):
    ctx = art[max(0, m.start()-50):m.end()+150].replace("\n"," ")
    print(f"  pos={m.start()}: {repr(ctx)}")

print("\n=== 길이 ===", len(art))
print("\n=== article_content 전체 (처음 2000자) ===")
print(repr(art[:2000]))
