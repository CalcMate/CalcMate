# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository
from modules.app_generator import generate_calculator

cfg = load_config()
repo = CalculatorRepository(get_db_adapter(cfg))
calcs = repo.get_all()

target = next((c for c in calcs if c.get("slug") == "severance-pay"), None)
if not target:
    print("[ERROR] severance-pay 계산기를 찾을 수 없음")
    sys.exit(1)

print("계산기:", target.get("name"), "/", target.get("slug"))
files = generate_calculator(target, cfg)

out_dir = Path(__file__).resolve().parent.parent / "data" / "workspace" / "severance-pay"
out_dir.mkdir(parents=True, exist_ok=True)

for fname in ("index.html", "style.css", "script.js"):
    content = files.get(fname, "")
    (out_dir / fname).write_text(content, encoding="utf-8")
    print(f"저장: {fname} ({len(content)}bytes)")

print("재생성 완료")
