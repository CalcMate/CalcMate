# -*- coding: utf-8 -*-
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

cfg = load_config(); db = get_db_adapter(cfg); repo = CalculatorRepository(db)
yt = next(c for c in repo.get_all() if c.get("slug") == "연말정산_환급액_계산기")
art = yt.get("article_content") or ""

FORM_PAT    = re.compile(r"<form[\s>]", re.IGNORECASE)
INPUT_PAT   = re.compile(r"<input[^>]+name=", re.IGNORECASE)
FORMULA_PAT = re.compile(r"공식은\s*['\"].*?[a-z_x*].*?['\"]")

errs = []
for pat, label in [(FORM_PAT,"구form"),(INPUT_PAT,"구input"),(FORMULA_PAT,"코드공식")]:
    ms = list(pat.finditer(art))
    if ms:
        errs.append(f"{label}: {len(ms)}건")

if errs:
    print("FAIL:", errs)
else:
    print("OK: 연말정산 article_content SP-8 PASS")

# script.js 확인
ws = Path(__file__).resolve().parent.parent / "data" / "workspace" / "연말정산_환급액_계산기"
script = (ws / "script.js").read_text(encoding="utf-8")
print(f"script.js: {len(script):,} chars")
for c in ["computeResult","total_salary","estimated_refund","_detail","_formula","notices","laborDeduction","incomeTax","creditLimit"]:
    print(f"  {'OK' if c in script else 'MISS'} {c}")
