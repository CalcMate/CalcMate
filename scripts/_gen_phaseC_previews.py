# -*- coding: utf-8 -*-
"""Phase C 나머지 6개 계산기 preview HTML 생성"""
import pathlib, sys

from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository
from modules.app_generator import generate_calculator, render_inline_calculator

cfg = load_config()
calcs = CalculatorRepository(get_db_adapter(cfg)).get_all()
target_slugs = [
    "weekly-holiday-allowance", "severance-pay", "annual-leave-allowance",
    "unemployment-benefit", "four-insurances", "육아휴직_급여_계산기"
]

for calc in calcs:
    slug = calc.get("slug", "")
    if slug not in target_slugs:
        continue
    files = generate_calculator(calc, cfg)
    fragment = render_inline_calculator(files)
    standalone = (
        "<!DOCTYPE html>\n<html lang='ko'><head>\n"
        "<meta charset='utf-8'>\n"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>\n"
        "<title>Phase C Preview — " + slug + "</title>\n"
        "</head><body style='margin:0;background:#F9FAFB'>\n"
        + fragment
        + "\n</body></html>"
    )
    out = pathlib.Path("data/workspace/preview_phaseC_" + slug + ".html")
    out.write_text(standalone, encoding="utf-8")
    print("OK:", out)

print("Done.")
