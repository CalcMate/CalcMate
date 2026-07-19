# -*- coding: utf-8 -*-
"""SP-8 감사 수정 검증: 4개 계산기 구 form 0건 + 주휴수당 faq[2] 자연어 확인."""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

ROOT      = Path(__file__).resolve().parent.parent
WORKSPACE = ROOT / "data" / "workspace"

cfg  = load_config()
db   = get_db_adapter(cfg)
repo = CalculatorRepository(db)
calcs = repo.get_all()

TARGETS = [
    ("weekly-holiday-allowance", "주휴수당",  "weekly-holiday-allowance"),
    ("unemployment-benefit",     "실업급여",  "unemployment-benefit"),
    ("four-insurances",          "4대보험",   "four-insurances"),
    ("annual-leave-allowance",   "연차수당",  "annual-leave-allowance"),
]

FORM_PAT  = re.compile(r'<form[\s>]', re.IGNORECASE)
INPUT_PAT = re.compile(r'<input[^>]+(?:id|name)=["\'][a-z_]+["\']', re.IGNORECASE)
# 코드 변수명: faq/article_content 텍스트 내 노출
CODE_VARS = [
    "hourly_wage", "weekly_hours", "avg_daily_wage", "employment_months",
    "monthly_salary", "daily_wage", "unused_days",
    "avg_monthly_wage", "leave_months",
]
# faq 코드 공식 패턴 — 영문 x / / 연산자 with 변수명
CODE_FORMULA_PAT = re.compile(r"공식은\s*['\"]|[a-z_]{4,}\s*[x×/\*]\s*[a-z_\d(]")

fails  = []
ok_log = []

for slug, name, dname in TARGETS:
    c = next((x for x in calcs if x.get("slug") == slug), None)
    art = c.get("article_content") or ""
    faq = json.loads(c.get("faq") or "[]")

    errs = []

    # ① article_content 구 form 태그 0건
    for hit in FORM_PAT.finditer(art):
        ex = art[max(0, hit.start()-20):hit.end()+40].replace("\n"," ")
        errs.append(f"  ❌ article_content 구 form 잔존: {repr(ex[:80])}")
    for hit in INPUT_PAT.finditer(art):
        ex = art[max(0, hit.start()-20):hit.end()+40].replace("\n"," ")
        errs.append(f"  ❌ article_content 구 input 잔존: {repr(ex[:80])}")

    # ② article_content 코드 변수명 0건
    for var in CODE_VARS:
        if var in art:
            idx = art.find(var)
            ex  = art[max(0,idx-10):idx+len(var)+20].replace("\n"," ")
            errs.append(f"  ❌ article_content 코드 변수명 '{var}': {repr(ex[:80])}")

    # ③ faq 코드 공식 패턴 0건
    for i, f in enumerate(faq):
        ans = f.get("answer", "")
        hit = CODE_FORMULA_PAT.search(ans)
        if hit:
            errs.append(f"  ❌ faq[{i}] 코드 공식 잔존: {repr(ans[:100])}")

    # ④ workspace index.html article 섹션에서도 form 0건
    html_path = WORKSPACE / dname / "index.html"
    if html_path.exists():
        html = html_path.read_text(encoding="utf-8")
        art_m = re.search(r'<article[^>]*>(.*?)</article>', html, re.DOTALL)
        if art_m:
            art_html = art_m.group(1)
            for hit in FORM_PAT.finditer(art_html):
                ex = art_html[max(0, hit.start()-20):hit.end()+40].replace("\n"," ")
                errs.append(f"  ❌ HTML article 구 form 잔존: {repr(ex[:80])}")

    if errs:
        fails.append((name, errs))
    else:
        ok_log.append(f"  ✅ {name}: PASS")

# ── 주휴수당 faq[2] 자연어 확인 ──────────────────────────────────────────────
wh = next((x for x in calcs if x.get("slug") == "weekly-holiday-allowance"), None)
faq_wh = json.loads(wh.get("faq") or "[]")
ans2 = faq_wh[2]["answer"] if len(faq_wh) > 2 else ""
if "x (" in ans2 or "공식은 '" in ans2:
    fails.append(("주휴수당 faq[2]", [f"  ❌ 코드 공식 잔존: {repr(ans2[:120])}"]))
else:
    ok_log.append(f"  ✅ 주휴수당 faq[2]: PASS — {repr(ans2[:80])}")

# ── 결과 출력 ─────────────────────────────────────────────────────────────────
print("=" * 60)
print(" SP-8 Verify — FORBIDDEN 패턴 검증")
print("=" * 60)
for msg in ok_log:
    print(msg)
if fails:
    print()
    for name, errs in fails:
        print(f"  [{name}]")
        for e in errs:
            print(e)
    print()
    print("❌ FAIL — 수정 필요")
    sys.exit(1)
else:
    print()
    print("=" * 60)
    print(" ✅ ALL PASS — 4개 계산기 구 form 0건, 코드 변수명 0건")
    print("=" * 60)
