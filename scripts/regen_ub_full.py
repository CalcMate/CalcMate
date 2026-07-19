# -*- coding: utf-8 -*-
"""Phase 2: unemployment-benefit index.html + script.js + style.css 전체 재생성"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository
from modules.app_generator import generate_calculator
from pathlib import Path

cfg = load_config()
db = get_db_adapter(cfg)
calc_repo = CalculatorRepository(db)
calcs = calc_repo.get_all()

ub = next((c for c in calcs if c.get("slug") == "unemployment-benefit"), None)
if not ub:
    print("[ERROR] unemployment-benefit 없음")
    sys.exit(1)

out_dir = Path("data/workspace/unemployment-benefit")
out_dir.mkdir(parents=True, exist_ok=True)

result = generate_calculator(ub, cfg)
updated = []
for fname, content in result.items():
    if not isinstance(content, str):
        continue
    (out_dir / fname).write_text(content, encoding="utf-8")
    updated.append(fname)
    print(f"  [갱신] {fname} ({len(content)}자)")

print(f"[완료] {len(updated)}개 파일 재생성")
