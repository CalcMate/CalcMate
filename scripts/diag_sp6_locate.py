# -*- coding: utf-8 -*-
"""SP-6 — 상여금/초과근무수당 관련 오류 문구 전수 확인"""
import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

ROOT = Path(__file__).resolve().parent.parent

cfg = load_config()
db = get_db_adapter(cfg)
calc_repo = CalculatorRepository(db)
calcs = calc_repo.get_all()

SP6_SLUG = "severance-pay"
# 오류 문구 패턴 (정규화 후 검색)
ERROR_PATTERNS = [
    "초과근무수당이나상여금은포함하지않아야",
    "초과근무수당이나상여금을포함하여",    # FAQ 4번 오해 서술
    "기본급과법정수당만포함",
    "상여금은포함하지않",
]

def norm(s): return re.sub(r"\s+", "", str(s or ""))

print("="*70)
print(" SP-6 오류 문구 위치 전수 확인")
print("="*70)

calc = next((c for c in calcs if c.get("slug") == SP6_SLUG), None)
if not calc:
    print("[없음] severance-pay 계산기")
    raise SystemExit

# 1. DB faq
print("\n[DB faq]")
faq_raw = calc.get("faq") or "[]"
faq = json.loads(faq_raw) if isinstance(faq_raw, str) else faq_raw
for i, item in enumerate(faq, 1):
    a = item.get("answer") or item.get("a") or ""
    q = item.get("question") or item.get("q") or ""
    a_norm = norm(a)
    hits = [p for p in ERROR_PATTERNS if p in a_norm]
    if hits:
        print(f"  [FAQ {i}] Q: {q}")
        print(f"          A: {a[:150]}")
        print(f"          오류패턴: {hits}")

# 2. DB article_content
print("\n[DB article_content]")
ac = calc.get("article_content") or ""
ac_lines = ac.splitlines()
for i, line in enumerate(ac_lines, 1):
    ln = norm(line)
    hits = [p for p in ERROR_PATTERNS if p in ln]
    if hits:
        print(f"  L{i}: {line.strip()[:150]}")
        print(f"  오류패턴: {hits}")

# 3. 생성된 HTML
print("\n[workspace HTML]")
html = ROOT / "data/workspace/severance-pay/index.html"
if html.exists():
    lines = html.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, 1):
        ln = norm(line)
        hits = [p for p in ERROR_PATTERNS if p in ln]
        if hits:
            print(f"  L{i}: {line.strip()[:150]}")
            print(f"  오류패턴: {hits}")
else:
    print("  index.html 없음")

# 4. 모순 없음 확인 — "포함" 관련 전체 서술 열거
print("\n[전체 '상여금' 언급 목록]")
for src_name, src_text in [("faq", json.dumps(faq, ensure_ascii=False)),
                             ("article_content", ac)]:
    lines = src_text.splitlines()
    for i, line in enumerate(lines, 1):
        if "상여금" in line or "초과근무" in line or "초과 근무" in line:
            print(f"  [{src_name} L{i}] {line.strip()[:150]}")
