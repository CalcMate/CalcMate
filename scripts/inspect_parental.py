# -*- coding: utf-8 -*-
"""육아휴직급여 계산기 전체 상태 출력."""
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

# slug 탐색
pl = None
for c in calcs:
    slug = c.get("slug", "")
    name = c.get("name", "")
    if "육아" in name or "parental" in slug.lower() or "육아" in slug:
        pl = c
        break

if not pl:
    print("[목록] 전체 슬러그:")
    for c in calcs:
        print(f"  {c.get('slug')} | {c.get('name')}")
    sys.exit(0)

print(f"[계산기] slug={pl.get('slug')} | name={pl.get('name')} | id={pl.get('id')}")
print()

# inputs
inputs_raw = pl.get("inputs")
if inputs_raw:
    inputs = json.loads(inputs_raw) if isinstance(inputs_raw, str) else inputs_raw
    print(f"=== inputs ({len(inputs)}개) ===")
    for inp in inputs:
        print(f"  {inp}")
    print()

# outputs
outputs_raw = pl.get("outputs")
if outputs_raw:
    outputs = json.loads(outputs_raw) if isinstance(outputs_raw, str) else outputs_raw
    print(f"=== outputs ({len(outputs)}개) ===")
    for o in outputs:
        print(f"  {o}")
    print()

# formula_engine
fe = pl.get("formula_engine") or ""
print(f"=== formula_engine ({len(fe)}자) ===")
print(fe)
print()

# FAQ
faq_raw = pl.get("faq") or "[]"
faq = json.loads(faq_raw) if isinstance(faq_raw, str) else faq_raw
print(f"=== FAQ ({len(faq)}개) ===")
for i, f in enumerate(faq):
    print(f"[{i}] Q: {f['question']}")
    print(f"    A: {f['answer']}")
    print()

# article_content
art = pl.get("article_content") or ""
print(f"=== article_content ({len(art)}자) ===")
print(art)
