# -*- coding: utf-8 -*-
"""실업급여 계산기 DB 설정 전체 덤프"""
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

calc = next((c for c in calcs if c.get("slug") == "unemployment-benefit"), None)
if not calc:
    print("[없음] unemployment-benefit")
    raise SystemExit

SKIP_LARGE = {"faq", "article_content"}

print("="*70)
print(" unemployment-benefit DB 설정 전체")
print("="*70)
for k, v in calc.items():
    if k in SKIP_LARGE:
        v_str = str(v or "")[:120] + "..." if len(str(v or "")) > 120 else str(v or "")
        print(f"  [{k}] (truncated) {v_str}")
    else:
        print(f"  [{k}] {v}")

# formula, input_schema, output_schema, compute_rules 상세 파싱
print("\n" + "="*70)
print(" 핵심 스키마 상세")
print("="*70)
for field in ["formula", "input_schema", "output_schema", "compute_rules"]:
    raw = calc.get(field)
    print(f"\n[{field}]")
    if raw:
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            print(json.dumps(parsed, ensure_ascii=False, indent=2))
        except Exception:
            print(raw)
    else:
        print("  (없음)")

# faq 항목
print("\n" + "="*70)
print(" DB faq 항목")
print("="*70)
faq_raw = calc.get("faq") or "[]"
try:
    faq = json.loads(faq_raw) if isinstance(faq_raw, str) else faq_raw
    for i, item in enumerate(faq, 1):
        q = item.get("question") or item.get("q") or ""
        a = item.get("answer") or item.get("a") or ""
        print(f"\n  [{i}] Q: {q}")
        print(f"       A: {a[:200]}")
except Exception:
    print(faq_raw[:500])
