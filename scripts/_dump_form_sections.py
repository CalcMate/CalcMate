# -*- coding: utf-8 -*-
"""각 계산기 article_content에서 제거할 전체 섹션 repr 출력."""
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

    # form 위치
    fm = re.search(r'<form[\s>]', art)
    if not fm:
        print(f"\n[{name}] form 없음"); continue

    # form 이전 h2 위치 (가장 마지막 \n\n<h2>)
    before     = art[:fm.start()]
    h2_matches = list(re.finditer(r'\n\n<h2>', before))
    if h2_matches:
        sec_start = h2_matches[-1].start()
    else:
        sec_start = max(0, fm.start() - 200)

    # form 블록 끝
    fm_end_m = re.search(r'</form>', art[fm.start():])
    if fm_end_m:
        form_end = fm.start() + fm_end_m.end()
    else:
        form_end = fm.start() + 300

    # form 이후 다음 h2 블록 (결과/결과해설) 끝 찾기
    after = art[form_end:]
    # 결과 섹션: form 바로 다음에 오는 \n\n<h2>...<p>...</p> 또는 \n\n<h2>...<ul>...</ul>
    # 다음 \n\n<h2> 를 찾고, 그 블록의 끝을 찾음
    next_section = re.search(r'\n\n<h2>', after)
    if next_section:
        # 이 섹션이 "결과" 관련인지 확인
        title_m = re.search(r'<h2>(.*?)</h2>', after[next_section.start():], re.DOTALL)
        title   = title_m.group(1) if title_m else ""
        if any(k in title for k in ["결과", "2.", "안내"]):
            # 다다음 \n\n<h2> 혹은 \n\n<hr> 혹은 문서 끝
            section2_after = after[next_section.start():]
            next_next = re.search(r'\n\n<(?:h2|hr|h3)', section2_after[1:])
            if next_next:
                sec_end = form_end + next_section.start() + 1 + next_next.start()
            else:
                sec_end = len(art)
        else:
            sec_end = form_end
    else:
        sec_end = form_end

    block = art[sec_start:sec_end]
    print(f"\n{'='*70}")
    print(f" [{name}] 제거 대상 전체 (chars {sec_start}~{sec_end}, len={len(block)})")
    print(f"{'='*70}")
    print(repr(block))
    # faq[2]
    faq = json.loads(c.get("faq") or "[]")
    if len(faq) > 2:
        print(f"\n  faq[2].answer = {repr(faq[2]['answer'])}")
