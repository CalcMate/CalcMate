# -*- coding: utf-8 -*-
"""SP-2 — 3개 계산기 HTML 재생성 (DB faq 수정 후)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository
from modules.app_generator import generate_calculator

TARGETS = ["severance-pay", "연말정산_환급액_계산기", "육아휴직_급여_계산기"]

cfg = load_config()
db = get_db_adapter(cfg)
calc_repo = CalculatorRepository(db)
calcs = calc_repo.get_all()
ROOT = Path(__file__).resolve().parent.parent

print("="*60)
print(" SP-2 계산기 HTML 재생성")
print("="*60)

for slug in TARGETS:
    calc = next((c for c in calcs if c.get("slug") == slug), None)
    if not calc:
        print(f"\n[SKIP] {slug} — 계산기 없음")
        continue

    out_dir = ROOT / "data" / "workspace" / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        files = generate_calculator(calc, cfg)
        for fname, content in files.items():
            if not isinstance(content, str):
                continue
            (out_dir / fname).write_text(content, encoding="utf-8")
            size = len(content.encode("utf-8"))
            print(f"\n[OK] {slug}/{fname}  {size:,} bytes")
    except Exception as e:
        import traceback
        print(f"\n[ERROR] {slug}: {e}")
        traceback.print_exc()

print("\n" + "="*60)
print("재생성 완료.")
