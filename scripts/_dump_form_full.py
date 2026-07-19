# -*- coding: utf-8 -*-
"""각 계산기 article_content form 블록 + 결과 섹션 전체 repr."""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

cfg = load_config(); db = get_db_adapter(cfg); repo = CalculatorRepository(db)
calcs = repo.get_all()

TARGETS = [
    ("weekly-holiday-allowance", "주휴수당"),
    ("unemployment-benefit", "실업급여"),
    ("four-insurances", "4대보험"),
    ("annual-leave-allowance", "연차수당"),
]

for slug, name in TARGETS:
    c   = next((x for x in calcs if x.get("slug") == slug), None)
    art = c.get("article_content") or ""
    # form 시작 위치 찾기
    fm  = re.search(r'<form[\s>]', art)
    if not fm:
        print(f"[{name}] form 없음\n"); continue
    # form 이전 h2 시작 위치
    before = art[:fm.start()]
    h2m    = list(re.finditer(r'\n\n<h2>', before))
    if h2m:
        section_start = h2m[-1].start()
    else:
        section_start = max(0, fm.start() - 50)
    # form 이후 계산 원리 h2 위치 찾기
    after_form = art[fm.start():]
    calc_m = re.search(r'\n\n<h2>(?!.*결과).*?</h2>', after_form)  # 계산 원리 h2
    if calc_m:
        section_end = fm.start() + calc_m.start()
    else:
        section_end = min(len(art), fm.start() + 1000)

    print(f"\n{'='*60}")
    print(f" [{name}] 제거 대상 블록 repr")
    print(f"{'='*60}")
    print(repr(art[section_start:section_end]))
    print(f"\n  section_start={section_start}, section_end={section_end}")
