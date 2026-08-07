# -*- coding: utf-8 -*-
"""연말정산 FAQ + article_content 내부 변수명 노출 grep."""
import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

cfg = load_config(); db = get_db_adapter(cfg); repo = CalculatorRepository(db)
yt = next(c for c in repo.get_all() if c.get("slug") == "연말정산_환급액_계산기")

# 검사 대상 변수명 패턴
VAR_PAT = re.compile(
    r'\b('
    r'total_salary|paid_tax|family_count|'
    r'labor_income|labor_deduction|gross_income|'
    r'income_tax|personal_deduction|insurance_deduction|'
    r'taxable_income|gross_tax|tax_credit|determined_tax|'
    r'local_income_tax|estimated_refund|'
    r'total_income|deductions|'          # 구 변수명도 포함
    r'np_m|hi_m|ltc_m|ei_m'
    r')\b'
)

results = {}

# ① article_content
art = yt.get("article_content") or ""
art_hits = [(m.group(), art[max(0,m.start()-30):m.end()+30].replace("\n"," "))
            for m in VAR_PAT.finditer(art)]
results["article_content"] = art_hits

# ② faq (각 Q+A 텍스트)
faq_raw = yt.get("faq") or "[]"
faq = json.loads(faq_raw) if isinstance(faq_raw, str) else faq_raw
faq_hits = []
for i, f in enumerate(faq):
    text = f.get("question","") + " " + f.get("answer","")
    for m in VAR_PAT.finditer(text):
        faq_hits.append((i, m.group(), text[max(0,m.start()-30):m.end()+30]))
results["faq"] = faq_hits

# 보고
print("="*60)
print("[grep 패턴]", VAR_PAT.pattern[:80])
print("="*60)
for field, hits in results.items():
    if hits:
        print(f"\n❌ {field}: {len(hits)}건")
        for h in hits:
            print(f"  → {h}")
    else:
        print(f"\n✅ {field}: 0건")

total = sum(len(v) for v in results.values())
print("\n" + "="*60)
if total == 0:
    print("✅ PASS — 내부 변수명 0건")
else:
    print(f"❌ FAIL — 총 {total}건")
print("="*60)
