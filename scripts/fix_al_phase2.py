# -*- coding: utf-8 -*-
"""연차수당 계산기 Phase 2 콘텐츠 수정.

수정 범위:
  AL-4: FAQ[1] 원칙-예외 구조 재서술 (제61조 요건 구체화)
        근거: 근로기준법 제60조제5항, 제36조, 제61조
  AL-7: FAQ[2] + article_content "일급" → "통상임금(일급)" 병기
  일관성: FAQ / article_content HTML FAQ 목록 / article_content 본문 3곳 동일 구조 검증

제61조 촉진제도 면제 요건 (재검증):
  사용기간 만료 6개월 전 — 미사용 휴가 일수 서면 통지
  근로자가 사용 계획 미제출 시 — 사용 시기를 서면으로 지정하여 통보
  위 두 절차를 모두 이행한 경우에만 지급의무 면제
"""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

cfg  = load_config()
db   = get_db_adapter(cfg)
repo = CalculatorRepository(db)
calcs = repo.get_all()
al = next((c for c in calcs if c.get("slug") == "annual-leave-allowance"), None)
assert al, "annual-leave-allowance 없음"
calc_id = al["id"]

faq = json.loads(al.get("faq") or "[]")
art = al.get("article_content") or ""

print(f"[로드] faq {len(faq)}개, article_content {len(art)}자")
print()

# ═══════════════════════════════════════════════════════════════════════════════
# AL-4: FAQ[1] — 원칙-예외 구조로 재서술 (제61조 요건 구체화)
# 현재: 예외→원칙 순서 (Phase 1 수정, 구조 미완)
# 목표: 원칙 먼저 → 예외(① 모두 사용, ② 제61조 완전 이행) → 결론
# ═══════════════════════════════════════════════════════════════════════════════
faq1_old = faq[1]["answer"]
faq[1]["answer"] = (
    "미사용 연차수당은 원칙적으로 사용자가 반드시 지급해야 합니다"
    "(근로기준법 제60조제5항·제36조 금품 청산). "
    "예외는 두 가지뿐입니다. "
    "① 해당 연도 연차를 이미 모두 사용한 경우, "
    "② 사용자가 근로기준법 제61조 연차 사용 촉진제도를 적법하게 이행한 경우 — "
    "사용기간 만료 6개월 전 미사용 일수 서면 통지 및 근로자 미계획 시 사용 시기 서면 지정, "
    "두 절차를 모두 완료한 때만 지급의무가 면제됩니다. "
    "이 두 경우에 해당하지 않는 한 '계약 해지 후라서 지급 안 된다'는 말은 사실이 아닙니다."
)
print("[AL-4] FAQ[1] 원칙-예외 재서술")
print(f"  이전: {faq1_old[:80]}...")
print(f"  이후: {faq[1]['answer'][:80]}...")
print()

# ═══════════════════════════════════════════════════════════════════════════════
# AL-7: FAQ[2] — "일급" → "통상임금(일급)" 병기
# ═══════════════════════════════════════════════════════════════════════════════
faq2_old = faq[2]["answer"]
faq[2]["answer"] = (
    "연차수당은 '통상임금(일급) × 미사용 일수'로 계산됩니다. "
    "예를 들어, 통상임금(일급)이 10만원이고 미사용 연차일이 5일이라면 "
    "연차수당은 50만원이 됩니다. "
    "통상임금은 기본급뿐만 아니라 정기적·일률적으로 지급되는 고정 수당을 포함하므로, "
    "기본급만으로 계산하지 않도록 주의하세요(근로기준법 시행령 제6조)."
)
print("[AL-7] FAQ[2] 통상임금 병기")
print(f"  이전: {faq2_old[:60]}...")
print(f"  이후: {faq[2]['answer'][:60]}...")
print()

# ═══════════════════════════════════════════════════════════════════════════════
# article_content 수정
# ═══════════════════════════════════════════════════════════════════════════════
art_new = art

# ── AL-4: HTML FAQ 목록 "연차수당을 받을 수 없는 경우" → 원칙-예외 구조 ────────
# Phase 1에서 수정된 현재 내용 → 원칙 먼저 오도록 재서술
art_new = art_new.replace(
    "미사용 연차수당을 받지 못하는 경우는 크게 두 가지입니다. "
    "① 해당 연도 연차를 이미 모두 사용한 경우, "
    "② 근로기준법 제61조에 따른 연차 사용 촉진제도가 적법하게 시행된 경우입니다. "
    "퇴직 시 미사용 연차수당은 원칙적으로 사용자가 지급해야 합니다(근로기준법 제36조).",
    "미사용 연차수당은 원칙적으로 사용자가 반드시 지급해야 합니다"
    "(근로기준법 제60조제5항·제36조). "
    "예외는 두 가지뿐입니다. "
    "① 해당 연도 연차를 이미 모두 사용한 경우, "
    "② 사용자가 근로기준법 제61조 연차 사용 촉진제도를 적법하게 이행한 경우 — "
    "사용기간 만료 6개월 전 서면 통지 및 사용 시기 서면 지정을 모두 완료한 때만 면제됩니다."
)

# ── AL-7: HTML FAQ 목록 "계산은 어떻게" → 통상임금 병기 ─────────────────────
art_new = art_new.replace(
    "연차수당은 '일급 x 미사용일 수'로 계산됩니다. "
    "예를 들어, 일급이 10만원이고 미사용 연차일이 5일이라면 연차수당은 50만원이 됩니다.",
    "연차수당은 '통상임금(일급) × 미사용 일수'로 계산됩니다. "
    "예를 들어, 통상임금(일급)이 10만원이고 미사용 연차일이 5일이라면 연차수당은 50만원이 됩니다."
)

# ── AL-7: 계산 원리 본문 — "일급에 미사용일 수를 곱해서" 부분 통상임금 명시 ──
art_new = art_new.replace(
    "연차수당은 사용하지 않은 연차에 대해 지급되는 금액으로, '일급에 미사용일 수를 곱해서 계산됩니다.'",
    "연차수당은 사용하지 않은 연차에 대해 지급되는 금액으로, '통상임금(일급)에 미사용 일수를 곱해서 계산됩니다'(근로기준법 시행령 제6조)."
)

# ── AL-4 일관성: 주의사항 본문에 원칙-예외 1문장 추가 (3번째 위치) ───────────
# 기존 "주의사항" 섹션 마지막에 지급 의무 원칙 한 줄 추가
art_new = art_new.replace(
    "<h2>주의사항</h2>\n<p>연차수당을 요청하기 전, 미사용 연차일 수와 일급이 정확한지 반드시 확인해야 합니다. "
    "또한, 회사 내규에 따라 연차수당 지급 절차가 상이할 수 있으니, 조율이 필요할 수 있습니다. "
    "연차수당 청구 시 관련 서류를 준비하는 것이 중요합니다. "
    "이와 함께, 연차수당은 일정 기간 내에 청구해야 하므로 기한을 준수하는 것도 필수적입니다.</p>",
    "<h2>주의사항</h2>\n<p>연차수당을 요청하기 전, 미사용 연차일 수와 통상임금(일급)이 정확한지 반드시 확인해야 합니다. "
    "또한, 회사 내규에 따라 연차수당 지급 절차가 상이할 수 있으니, 조율이 필요할 수 있습니다. "
    "연차수당 청구 시 관련 서류를 준비하는 것이 중요합니다. "
    "이와 함께, 연차수당은 일정 기간 내에 청구해야 하므로 기한을 준수하는 것도 필수적입니다. "
    "미사용 연차수당은 원칙적으로 사용자가 지급해야 하며, "
    "근로기준법 제61조 촉진제도를 적법하게 이행한 경우에만 예외적으로 면제됩니다.</p>"
)

# ── AL-7: 결과 해설 — "입력한 일급과" 통상임금 병기 ────────────────────────
art_new = art_new.replace(
    "입력한 일급과 미사용 연차 일수를 바탕으로 연차수당이 계산됩니다. "
    "예를 들어, 일급이 100,000원이고 미사용 연차가 5일이라면 연차수당은 500,000원이 됩니다. "
    "간편하게 계산을 통해 정확한 금액을 확인해 보세요.",
    "입력한 통상임금(일급)과 미사용 연차 일수를 바탕으로 연차수당이 계산됩니다. "
    "예를 들어, 통상임금(일급)이 100,000원이고 미사용 연차가 5일이라면 연차수당은 500,000원이 됩니다. "
    "간편하게 계산을 통해 정확한 금액을 확인해 보세요."
)

# ── AL-7: form label — "일급 (원)" → "통상임금(일급, 원)" ────────────────────
art_new = art_new.replace(
    '<label for="daily_wage">일급 (원): </label>',
    '<label for="daily_wage">통상임금(일급, 원): </label>'
)

# ── AL-7: Call to Action — "일급과" → "통상임금(일급)과" ─────────────────────
art_new = art_new.replace(
    "본인의 일급과 미사용 연차를 입력하여 간편하게 연차수당을 계산해 보세요!",
    "본인의 통상임금(일급)과 미사용 연차를 입력하여 간편하게 연차수당을 계산해 보세요!"
)

if art_new == art:
    print("[경고] article_content 변경 없음 — 교체 대상 문자열 불일치 가능성")
else:
    print(f"[AL-4/7] article_content 수정 완료 ({len(art)}자 → {len(art_new)}자)")
print()

# ── DB 저장 ───────────────────────────────────────────────────────────────────
repo.update(calc_id, {
    "faq": json.dumps(faq, ensure_ascii=False),
    "article_content": art_new,
})
print("[DB] faq + article_content 저장 완료")
print()

# ═══════════════════════════════════════════════════════════════════════════════
# 검증: 원칙-예외 일관성 3곳 전수 확인
# ═══════════════════════════════════════════════════════════════════════════════
calcs2 = repo.get_all()
al2 = next((c for c in calcs2 if c.get("slug") == "annual-leave-allowance"), None)
faq2 = json.loads(al2.get("faq") or "[]")
art2 = al2.get("article_content") or ""

print("=" * 60)
print(" 원칙-예외 일관성 검증 (3곳)")
print("=" * 60)

PRINCIPLE = "원칙적으로 사용자가"
EXCEPTION  = "제61조"

checks3 = [
    ("FAQ[1] (structured)", faq2[1]["answer"]),
    ("article HTML FAQ 목록", art2),
    ("article 주의사항 본문", art2),
]

ok = True
for loc, text in checks3:
    has_p = PRINCIPLE in text
    has_e  = EXCEPTION  in text
    status = "OK" if (has_p and has_e) else "NG"
    if status == "NG":
        ok = False
    print(f"  [{status}] {loc}: 원칙={has_p}, 예외={has_e}")

print()

# ── AL-7: 통상임금 병기 확인 ─────────────────────────────────────────────────
print("=" * 60)
print(" AL-7 통상임금 병기 확인")
print("=" * 60)

tosang_checks = [
    ("FAQ[2] answer", faq2[2]["answer"]),
    ("article HTML FAQ '계산은 어떻게'", art2),
    ("article 계산 원리 본문", art2),
    ("article 주의사항 본문", art2),
]
for loc, text in tosang_checks:
    has = "통상임금" in text
    status = "OK" if has else "NG"
    if not has:
        ok = False
    print(f"  [{status}] {loc}")

print()

# ── 금지 문구 잔존 0건 확인 ──────────────────────────────────────────────────
print("=" * 60)
print(" 금지 문구 잔존 확인")
print("=" * 60)
combined = " ".join(f["answer"] for f in faq2) + " " + art2
forbidden = [
    "기본 일급만 기준",
    "지급되지 않을 수 있",
    "지급 안 될 수 있",
]
for phrase in forbidden:
    count = combined.count(phrase)
    status = "OK" if count == 0 else f"NG ({count}건 잔존!)"
    print(f"  [{status}] '{phrase}'")
    if count > 0:
        ok = False

print()
if ok:
    print(">>> 모든 검증 PASS")
else:
    print(">>> 일부 검증 실패 — 위 NG 항목 확인 필요")
    sys.exit(1)
