# -*- coding: utf-8 -*-
"""annual-leave-allowance HTML 재생성."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository
from modules.app_generator import generate_calculator

cfg = load_config()
db  = get_db_adapter(cfg)
repo = CalculatorRepository(db)
calcs = repo.get_all()
calc = next((c for c in calcs if c.get("slug") == "annual-leave-allowance"), None)
assert calc, "annual-leave-allowance 없음"

ROOT = Path(__file__).resolve().parent.parent
out_dir = ROOT / "data" / "workspace" / "annual-leave-allowance"
out_dir.mkdir(parents=True, exist_ok=True)

result = generate_calculator(calc, cfg)
for fname, content in result.items():
    if not isinstance(content, str):
        print(f"[{fname}] {content}")
        continue
    (out_dir / fname).write_text(content, encoding="utf-8")
    print(f"[OK] {fname}  {len(content.encode('utf-8')):,} bytes")

print("\nDone — annual-leave-allowance 재생성 완료")
