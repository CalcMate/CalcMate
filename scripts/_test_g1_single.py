# -*- coding: utf-8 -*-
"""주휴수당 1건 단발 생성 → G1/G3/G4 통과 확인 (DB 저장 없음)."""
import sys, json
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from modules.calculator_pipeline import _write_article, _load_legal_basis
from modules.calculator_seo_generator import generate_seo
from modules.calculator_faq_generator import generate_faq
from modules.publish_quality import check_publish_quality, _plain_text
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

cfg = load_config()
repo = CalculatorRepository(get_db_adapter(cfg))

TARGET_SLUG = "weekly-holiday-allowance"
KEYWORD = "주휴수당 계산"

calc = next((c for c in repo.get_all() if str(c.get("slug","")) == TARGET_SLUG), None)
if not calc:
    print(f"[ERROR] 계산기 없음: {TARGET_SLUG}")
    sys.exit(1)
print(f"[OK] 계산기 로드: {calc.get('name')}  (slug={TARGET_SLUG})")

seo = generate_seo(cfg, calc.get("name", KEYWORD), KEYWORD)
print(f"[OK] SEO 생성: title={seo.get('title','')[:40]}")

faq = []
if calc.get("faq"):
    try:
        faq = json.loads(calc["faq"]) if isinstance(calc["faq"], str) else calc["faq"]
    except Exception:
        faq = []
if not faq:
    faq = generate_faq(cfg, calc.get("name", KEYWORD))
print(f"[OK] FAQ: {len(faq)}개")

print("\n[..] 본문 생성 중 (GPT 호출)...")
body_html, meta = _write_article(cfg, calc, KEYWORD, seo, faq)
plain_len = len(_plain_text(body_html))
print(f"[OK] 생성 완료: {plain_len}자 (plain text)")

print("\n[..] 품질 검사...")
qc = check_publish_quality(cfg, body_html, body_html, calc, link_pool_size=2)
result = qc.get("result", "?")
failed = qc.get("failed_rules") or []
passed = qc.get("passed_rules") or []

print(f"\n결과: {result}")
print(f"통과 게이트: {[r['gate'] for r in passed]}")
if failed:
    print(f"실패 게이트:")
    for r in failed:
        print(f"  [{r['gate']}] {r.get('message','')}")
else:
    print("실패 게이트: 없음 (모두 통과)")

# 실제로 failed_rules에 있으면 FAIL, 없으면 PASS
failed_gates = {r["gate"] for r in failed}
print(f"\nG1 (분량 {plain_len}자): {'PASS' if 'G1' not in failed_gates else 'FAIL'}")
print(f"G3 (FAQ):              {'PASS' if 'G3' not in failed_gates else 'FAIL'}")
print(f"G4 (예시):             {'PASS' if 'G4' not in failed_gates else 'FAIL'}")
print(f"G5 (내부링크):         {'PASS' if 'G5' not in failed_gates else 'FAIL (테스트환경 정상)'}")
print(f"G6 (CTA):              {'PASS' if 'G6' not in failed_gates else 'FAIL (테스트환경 정상)'}")

print("\n" + "="*60)
print("생성된 HTML (전체):")
print("="*60)
print(body_html)
