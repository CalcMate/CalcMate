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
fi = next((c for c in calcs if c.get("slug") == "four-insurances"), None)

faq = json.loads(fi.get("faq") or "[]")
print("=== DB faq ===")
for i, item in enumerate(faq):
    print(f"[{i}] Q: {item.get('question','')[:80]}")
    print(f"    A: {item.get('answer','')[:200]}")
    print()

print("=== article_content ===")
print(fi.get("article_content","")[:3000])
