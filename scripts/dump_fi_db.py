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

SKIP = {"faq", "article_content"}
for k, v in fi.items():
    if k in SKIP:
        print(f"[{k}] (truncated) {str(v or '')[:80]}...")
    else:
        print(f"[{k}] {v}")

for field in ["formula", "input_schema", "output_schema", "compute_rules"]:
    raw = fi.get(field)
    print(f"\n=== {field} ===")
    if raw:
        try:
            print(json.dumps(json.loads(raw) if isinstance(raw, str) else raw, ensure_ascii=False, indent=2))
        except Exception:
            print(raw)
    else:
        print("(없음)")
