# -*- coding: utf-8 -*-
"""육아휴직급여 계산기 DB 스키마 상세 확인."""
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
pl = next((c for c in calcs if c.get("slug") == "육아휴직_급여_계산기"), None)

# DB 필드 전체 키 목록
print("=== DB 필드 키 목록 ===")
for k, v in pl.items():
    if k in ("article_content", "faq"):
        print(f"  {k}: ({len(str(v))}자)")
    else:
        print(f"  {k}: {repr(v)[:120]}")
print()

# input_schema, output_schema, formula 필드
print("=== input_schema ===")
print(repr(pl.get("input_schema")))
print()
print("=== output_schema ===")
print(repr(pl.get("output_schema")))
print()
print("=== formula ===")
print(repr(pl.get("formula")))
print()
print("=== inputs (legacy) ===")
print(repr(pl.get("inputs")))
print()
print("=== outputs (legacy) ===")
print(repr(pl.get("outputs")))
print()
print("=== calculator_type ===")
print(repr(pl.get("calculator_type")))
print()
print("=== compute_type ===")
print(repr(pl.get("compute_type")))
