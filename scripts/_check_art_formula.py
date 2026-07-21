# -*- coding: utf-8 -*-
"""6개 Verified 계산기 article_content 내 코드 공식 / 구 form 잔존 최종 확인."""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

cfg = load_config(); db = get_db_adapter(cfg); repo = CalculatorRepository(db)
calcs = repo.get_all()

SLUGS = [
    "weekly-holiday-allowance",
    "severance-pay",
    "unemployment-benefit",
    "four-insurances",
    "annual-leave-allowance",
    "육아휴직_급여_계산기",
]

FORM_PAT   = re.compile(r'<form[\s>]', re.IGNORECASE)
INPUT_PAT  = re.compile(r'<input[^>]+(?:id|name)=["\'][a-z_]+["\']', re.IGNORECASE)
FORMULA_PAT= re.compile(r"공식은\s*['\"].*?[a-z_x×/\*].*?['\"]")

ok = []
fail = []

for slug in SLUGS:
    c   = next((x for x in calcs if x.get("slug") == slug), None)
    art = c.get("article_content") or ""
    errs = []
    for pat, label in [(FORM_PAT, "구 form"), (INPUT_PAT, "구 input"), (FORMULA_PAT, "코드 공식")]:
        for m in pat.finditer(art):
            ctx = art[max(0,m.start()-20):m.end()+60].replace("\n"," ")
            errs.append(f"  [{label}] {repr(ctx[:100])}")
    if errs:
        fail.append((slug, errs))
    else:
        ok.append(f"  ✅ {slug}: PASS")

print("="*60)
for msg in ok: print(msg)
if fail:
    for slug, errs in fail:
        print(f"  ❌ {slug}:")
        for e in errs: print(e)
    print("\n❌ FAIL")
else:
    print("\n✅ ALL PASS — article_content 코드 공식/form 0건")
print("="*60)
