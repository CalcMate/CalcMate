# -*- coding: utf-8 -*-
"""연말정산 DB 데이터 확인."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

cfg = load_config(); db = get_db_adapter(cfg); repo = CalculatorRepository(db)
calcs = repo.get_all()
yt = next((c for c in calcs if "연말" in (c.get("slug") or "") or "연말" in (c.get("name") or "")), None)
if not yt:
    print("연말정산 DB 없음"); sys.exit(1)

print(f"slug: {yt.get('slug')}")
print(f"name: {yt.get('name')}")
print(f"\n--- inputs (config) ---")
cfg_raw = yt.get("config") or "{}"
calc_cfg = json.loads(cfg_raw) if isinstance(cfg_raw, str) else cfg_raw
print(json.dumps(calc_cfg.get("inputs", []), ensure_ascii=False, indent=2))
print(f"\n--- outputs ---")
print(json.dumps(calc_cfg.get("outputs", []), ensure_ascii=False, indent=2))
print(f"\n--- compute_js (처음 500자) ---")
print(repr((yt.get("compute_js") or "")[:500]))
print(f"\n--- faq (각 Q/A 요약) ---")
faq = json.loads(yt.get("faq") or "[]")
for i, f in enumerate(faq):
    print(f"  [{i}] Q: {f.get('question','')[:60]}")
    print(f"       A: {f.get('answer','')[:80]}")
