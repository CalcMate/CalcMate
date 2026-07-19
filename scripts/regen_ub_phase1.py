# -*- coding: utf-8 -*-
"""Phase 1: unemployment-benefit script.js 재생성 (계산 로직만)"""
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
    print("[ERROR] unemployment-benefit 계산기 없음")
    sys.exit(1)

out_dir = Path("data/workspace/unemployment-benefit")
out_dir.mkdir(parents=True, exist_ok=True)

print("[재생성 시작] unemployment-benefit")
result = generate_calculator(ub, cfg)
updated = []
for fname, content in result.items():
    if not isinstance(content, str):
        continue
    if fname == "script.js":
        (out_dir / fname).write_text(content, encoding="utf-8")
        updated.append(fname)
        print(f"  [갱신] {fname} ({len(content)}자)")

if not updated:
    print("[WARN] script.js 갱신 없음")
else:
    print("[완료] script.js 재생성 완료")
    print()
    # computeResult 구간 출력
    js = (out_dir / "script.js").read_text(encoding="utf-8")
    start = js.find("window.computeResult")
    end = js.find("};", start) + 2 if start != -1 else -1
    if start != -1:
        print("[script.js computeResult 블록]")
        print(js[start:end+1])
