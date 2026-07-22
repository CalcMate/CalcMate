# -*- coding: utf-8 -*-
"""Phase D 전체 preview HTML 재생성 + 검증"""
import re, pathlib, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository
from modules.app_generator import generate_calculator, render_inline_calculator

cfg = load_config()
calcs = CalculatorRepository(get_db_adapter(cfg)).get_all()
seen = set()
all_ok = True

for calc in calcs:
    slug = calc.get("slug", "")
    if slug in seen:
        continue
    seen.add(slug)

    files = generate_calculator(calc, cfg)
    html = files.get("index.html", "")
    js   = files.get("script.js", "")
    html_ns = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)

    ph_count = len(re.findall(r"data-ph=", html_ns))
    raw_ph   = re.findall(r"\{[A-Za-z_][A-Za-z0-9_]*\}", html_ns)
    has_cta  = "SM_CTA_RULES" in js
    has_faq  = "SM_DYNAMIC_FAQ" in js
    has_div  = "sm-dynamic-faq" in html

    ok = has_cta and has_faq and has_div and not raw_ph
    if not ok:
        all_ok = False
    status = "OK  " if ok else "FAIL"
    print(f"{status} {slug:<38} ph_spans={ph_count} raw_ph={len(raw_ph)} cta={has_cta} dyn_faq={has_faq}")

    # preview HTML 업데이트
    fragment = render_inline_calculator(files)
    out = pathlib.Path("data/workspace/preview_phaseD_" + slug + ".html")
    out.write_text(
        "<!DOCTYPE html><html lang=ko><head><meta charset=utf-8><title>Phase D - "
        + slug + "</title></head><body style='margin:0'>" + fragment + "</body></html>",
        encoding="utf-8"
    )

print()
print("Phase D build PASS" if all_ok else "Phase D build FAIL")
