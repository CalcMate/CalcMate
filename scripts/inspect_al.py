# -*- coding: utf-8 -*-
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

cfg = load_config()
db = get_db_adapter(cfg)
repo = CalculatorRepository(db)
calcs = repo.get_all()
al = next((c for c in calcs if c.get("slug") == "annual-leave-allowance"), None)
faq = json.loads(al.get("faq") or "[]")

print(f"=== FAQ ({len(faq)}개) ===")
for i, f in enumerate(faq):
    print(f"[{i}] Q: {f['question']}")
    print(f"    A: {f['answer']}")
    print()

print("=== article_content ===")
art = al.get("article_content") or ""
print(art)
