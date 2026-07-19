# -*- coding: utf-8 -*-
"""SP-6 — 퇴직금 계산기 상여금/초과근무수당 설명 오류 수정

법령 근거:
  근로기준법 제2조제1항제6호: 평균임금 = 사유 발생일 이전 3개월 지급 임금 총액 ÷ 3개월 총일수
  근로기준법 시행령 제2조: 평균임금 산정에서 제외되는 임금 항목 (임시 지급 수당, 1회성 급부 등)
  결론: 연장·야간·휴일 가산수당(초과근무수당), 통상 지급 상여금(연간총액의 1/12)은 포함 대상
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

cfg = load_config()
db = get_db_adapter(cfg)
calc_repo = CalculatorRepository(db)
calcs = calc_repo.get_all()

SLUG = "severance-pay"

# ── 교체 정의 ─────────────────────────────────────────────────────────
# article_content 주의사항 문장 교체
ARTICLE_OLD = (
    "평균 월급은 기본급과 법정수당만 포함해야 하며, "
    "초과 근무수당이나 상여금은 포함하지 않아야 합니다."
)
ARTICLE_NEW = (
    "평균임금은 퇴직 전 3개월 동안 지급된 임금 총액을 3개월 총 일수로 나눈 금액입니다. "
    "기본급뿐 아니라 연장·야간·휴일근로 가산수당과 통상적으로 지급된 상여금(연간 총액의 1/12)도 포함됩니다. "
    "임시로 지급된 수당이나 1회성 급부는 제외됩니다."
)

# DB faq[4] answer 교체 (Q: "퇴직금 계산 시 자주 틀리는 부분은 무엇인가요?")
FAQ_OLD = (
    "흔한 오해 중 하나는 초과 근무수당이나 상여금을 포함하여 평균 월급을 계산해야 한다는 "
    "것입니다. 평균 월급은 기본급과 법정수당만 포함하여 계산해야 합니다."
)
FAQ_NEW = (
    "가장 흔한 오류는 기본급만으로 평균임금을 산정하는 경우입니다. "
    "근로기준법 제2조에 따르면 연장·야간·휴일근로 가산수당과 통상적으로 지급되는 "
    "상여금(연간 총액의 1/12)도 평균임금에 포함됩니다. "
    "반면 임시로 지급된 수당이나 1회성 급부는 제외됩니다 "
    "(근로기준법 시행령 제2조)."
)

print("="*70)
print(" SP-6 상여금/초과근무수당 설명 오류 수정")
print("="*70)

calc = next((c for c in calcs if c.get("slug") == SLUG), None)
if not calc:
    print("[없음] severance-pay")
    raise SystemExit

calc_id = calc.get("id", "")

# ── 1. DB faq 수정 ────────────────────────────────────────────────────
faq_raw = calc.get("faq") or "[]"
faq = json.loads(faq_raw) if isinstance(faq_raw, str) else faq_raw
faq_changed = False
for item in faq:
    a = item.get("answer") or item.get("a") or ""
    if FAQ_OLD in a:
        key = "answer" if "answer" in item else "a"
        item[key] = a.replace(FAQ_OLD, FAQ_NEW)
        faq_changed = True
        q = item.get("question") or item.get("q") or ""
        print(f"\n[DB faq 수정]")
        print(f"  Q: {q}")
        print(f"  구: {FAQ_OLD[:80]}...")
        print(f"  신: {FAQ_NEW[:80]}...")

if faq_changed:
    calc_repo.update(calc_id, {"faq": json.dumps(faq, ensure_ascii=False)})
    print(f"  → faq DB 업데이트 완료 (id={calc_id})")
else:
    print("\n[SKIP] DB faq — 대상 문자열 없음")

# ── 2. DB article_content 수정 ────────────────────────────────────────
ac = calc.get("article_content") or ""
ac_changed = False

if ARTICLE_OLD in ac:
    ac = ac.replace(ARTICLE_OLD, ARTICLE_NEW)
    ac_changed = True
    print(f"\n[article_content 주의사항 수정]")
    print(f"  구: {ARTICLE_OLD[:80]}...")
    print(f"  신: {ARTICLE_NEW[:80]}...")
else:
    print("\n[SKIP] article_content 주의사항 — 대상 문자열 없음")

# article_content 안 FAQ 4번도 교체
if FAQ_OLD in ac:
    ac = ac.replace(FAQ_OLD, FAQ_NEW)
    ac_changed = True
    print(f"\n[article_content FAQ 4번 수정]")
    print(f"  구: {FAQ_OLD[:80]}...")
    print(f"  신: {FAQ_NEW[:80]}...")

if ac_changed:
    calc_repo.update(calc_id, {"article_content": ac})
    print(f"  → article_content DB 업데이트 완료 (id={calc_id})")

print("\n" + "="*70)
print("수정 완료. HTML 재생성을 실행하세요.")
