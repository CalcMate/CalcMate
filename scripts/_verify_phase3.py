# -*- coding: utf-8 -*-
"""Phase 3 검증 전용 — FORBIDDEN 패턴 0건 + C-13 일관성."""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = ROOT / "data" / "workspace"

cfg  = load_config()
db   = get_db_adapter(cfg)
repo = CalculatorRepository(db)
calcs = repo.get_all()

pl_final = next(c for c in calcs if c.get("slug") == "육아휴직_급여_계산기")
sp_final = next(c for c in calcs if c.get("slug") == "severance-pay")

pl_html     = (WORKSPACE / "육아휴직_급여_계산기" / "index.html").read_text(encoding="utf-8")
sp_html     = (WORKSPACE / "severance-pay" / "index.html").read_text(encoding="utf-8")
pl_db_str   = json.dumps({"faq": pl_final.get("faq"), "art": pl_final.get("article_content")}, ensure_ascii=False)
sp_db_str   = json.dumps({"faq": sp_final.get("faq"), "art": sp_final.get("article_content")}, ensure_ascii=False)

# 퇴직금 article/faq 섹션만 추출
sp_art_match = re.search(r'<article[^>]*>(.*?)</article>', sp_html, re.DOTALL)
sp_article   = sp_art_match.group(1) if sp_art_match else ""
sp_faq_match = re.search(r'class="[^"]*faq[^"]*"[^>]*>(.*?)</section>', sp_html, re.DOTALL)
sp_faq_sec   = sp_faq_match.group(1) if sp_faq_match else ""

print("=" * 60)
print(" FORBIDDEN 패턴 검증")
print("=" * 60)

fail = False
# 육아휴직 전체 (avg_monthly_wage 포함 — 새 엔진에 없음)
for phrase in ["avg_monthly_wage", "government_support_percentage",
               "company_policy_support_percentage", "leave_months", "14,400,000"]:
    for label, text in [("육아휴직 index.html", pl_html), ("육아휴직 DB", pl_db_str)]:
        cnt = text.count(phrase)
        if cnt > 0:
            print(f"  ❌ [{label}] '{phrase}': {cnt}건")
            fail = True

# 퇴직금 DB + article/faq 섹션 (index.html 계산기 form/JS는 정당하게 avg_monthly_wage 사용)
for phrase in ["avg_monthly_wage", "total_days / 365"]:
    for label, text in [
        ("퇴직금 DB", sp_db_str),
        ("퇴직금 article", sp_article),
        ("퇴직금 FAQ 섹션", sp_faq_sec),
    ]:
        cnt = text.count(phrase)
        if cnt > 0:
            print(f"  ❌ [{label}] '{phrase}': {cnt}건")
            fail = True

if not fail:
    print("  ✅ 모든 FORBIDDEN 패턴 0건")

# C-13 일관성
pl_faq_txt = json.loads(pl_final.get("faq") or "[]")[2]["answer"]
pl_art_txt = pl_final.get("article_content") or ""
c13_ok = (
    "통상임금의 80%"  in pl_faq_txt and "통상임금의 100%" in pl_faq_txt and
    "통상임금의 80%"  in pl_art_txt  and "통상임금의 100%" in pl_art_txt and
    "avg_monthly_wage" not in pl_faq_txt and
    "avg_monthly_wage" not in pl_art_txt
)
print(f"\n  C-13 (faq⟺article 80%/100% 일치): {'✅ PASS' if c13_ok else '❌ FAIL'}")

# 계산 예시 대조 (스크립트 계산값과 article_content 일치 여부)
examples = {
    "1,500,000원": "일반 300만 상한 적용",
    "1,440,000원": "일반 180만",
    "2,000,000원": "6+6 1개월 상한 적용",
    "2,500,000원": "6+6 3개월",
    "6,000,000원": "퇴직금 2년 300만",
}
print("\n  계산 예시 대조:")
ex_fail = False
for val, label in examples.items():
    in_pl = val in pl_art_txt or val in pl_html
    in_sp = val in sp_db_str or val in sp_html
    target = in_pl if "6,000,000" not in val else in_sp
    note = "✅" if target else "⚠️ 없음"
    print(f"    [{note}] {val} ({label})")
    if not target:
        ex_fail = True

print()
ok = not fail and c13_ok and not ex_fail
print("=== 검증 결과:", "✅ ALL PASS" if ok else "❌ 실패 있음 ===")
sys.exit(0 if ok else 1)
