# -*- coding: utf-8 -*-
import sys, json
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, __import__("pathlib").Path(__file__).resolve().parent.parent.__str__())
from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

cfg   = load_config()
db    = get_db_adapter(cfg)
repo  = CalculatorRepository(db)
calcs = repo.get_all()

pl  = next(c for c in calcs if c.get("slug") == "육아휴직_급여_계산기")
faq = json.loads(pl.get("faq") or "[]")
print("=== 육아휴직 faq ===")
for i, f in enumerate(faq):
    print(f"  [{i}] answer={repr(f['answer'][:150])}")

sp     = next(c for c in calcs if c.get("slug") == "severance-pay")
sp_faq = json.loads(sp.get("faq") or "[]")
print("\n=== 퇴직금 faq ===")
for i, f in enumerate(sp_faq):
    print(f"  [{i}] answer={repr(f['answer'][:150])}")

print("\n=== 퇴직금 article_content ===")
sp_art = sp.get("article_content") or ""
print(repr(sp_art[:3500]))
