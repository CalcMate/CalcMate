# -*- coding: utf-8 -*-
"""severance-pay / 육아휴직 계산기 article_content 필드 forbidden 확인"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

cfg = load_config()
db = get_db_adapter(cfg)
calc_repo = CalculatorRepository(db)
calcs = calc_repo.get_all()

TARGETS = {
    "severance-pay":        ["근로기준법 제34조"],
    "육아휴직_급여_계산기": ["고용보험법 제40조", "근로기준법 제74조"],
}

def norm(s): return re.sub(r"\s+", "", str(s or ""))

for slug, needles in TARGETS.items():
    calc = next((c for c in calcs if c.get("slug") == slug), None)
    if not calc:
        continue

    print(f"\n{'='*60}")
    print(f" {slug} — forbidden 있는 필드 탐색")
    print(f"{'='*60}")

    for field, val in calc.items():
        val_str = str(val or "")
        hits = [n for n in needles if norm(n) in norm(val_str)]
        if hits:
            # 해당 줄 표시
            lines = val_str.splitlines()
            for i, line in enumerate(lines, 1):
                if any(norm(n) in norm(line) for n in hits):
                    print(f"  필드='{field}' L{i}: {line.strip()[:120]}")
