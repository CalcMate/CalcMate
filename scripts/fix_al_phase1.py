# -*- coding: utf-8 -*-
"""연차수당 계산기 Phase 1 콘텐츠 수정.

수정 범위:
  AL-2 (Critical급): faq[3] 통상임금 정의 오류 정정
    "기본 일급만 기준" → 통상임금(기본급+고정수당) 정확 설명
    근거: 근로기준법 시행령 제6조 통상임금 산정

  AL-3 (Critical급): faq[1] 퇴직 후 미사용 연차 지급 원칙 오류 정정
    "지급 안 될 수 있다" → 의무 지급 원칙 + 제61조 예외만 존재
    근거: 근로기준법 제60조제5항, 제61조

조문 재검증 근거:
  - 통상임금: 근로기준법 제2조제1항제5호, 시행령 제6조
    "통상임금이란 근로자에게 정기적이고 일률적으로 소정근로 또는 총 근로에 대하여
     지급하기로 정한 시간급·일급·주급·월급 또는 도급 금액"
    실무 범위: 기본급 + 직책수당·직무수당·근속수당 등 정기·일률·고정 지급 수당
    미포함: 식비·교통비 등 실비변상, 성과급(지급조건 따라 상이)

  - 퇴직 시 미사용 연차수당: 연차유급휴가 미사용에 따른 금전 보상
    * 근로기준법 제60조제5항: 연차 사용 기간 통상임금 지급 의무
    * 근로기준법 제36조: 퇴직 후 14일 이내 금품 청산 의무 — 미사용 연차수당 포함
    * 단, 제61조 연차 사용 촉진제도 적법 시행 시 면제 가능
    * "지급 안 될 수 있다"는 표현은 전반적으로 잘못됨 — 촉진제도 예외만 존재
"""
import sys, os, json
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
print(f"[로드] faq {len(faq)}개")
print()

# ─── 전수 검색: 구 오류 문구 존재 확인 ────────────────────────────────────────
art = al.get("article_content") or ""
combined_before = " ".join(f["answer"] for f in faq) + " " + art

forbidden_before = [
    "기본 일급만 기준",
    "지급되지 않을 수 있",
    "지급 안 될 수 있",
]
print("=" * 60)
print(" 수정 전 오류 문구 전수 검색")
print("=" * 60)
for v in forbidden_before:
    count = combined_before.count(v)
    print(f"  '{v}': {count}건")
print()

# ═══════════════════════════════════════════════════════════════════════════════
# AL-3: faq[1] — 퇴직 후 미사용 연차 지급 원칙 오류 정정
# ═══════════════════════════════════════════════════════════════════════════════
faq1_old = faq[1]["answer"]
faq[1]["answer"] = (
    "미사용 연차수당을 받지 못하는 경우는 크게 두 가지입니다. "
    "① 해당 연도 연차를 이미 모두 사용한 경우, "
    "② 근로기준법 제61조에 따른 연차 사용 촉진제도가 사용자에 의해 적법하게 시행된 경우입니다. "
    "퇴직 시 미사용 연차에 대한 수당은 원칙적으로 사용자가 지급해야 합니다(근로기준법 제36조 금품 청산). "
    "단순히 '계약 해지 후라서 지급 안 된다'는 것은 사실이 아닙니다."
)
print("[AL-3] faq[1] 수정")
print(f"  이전: {faq1_old[:100]}...")
print(f"  이후: {faq[1]['answer'][:100]}...")
print()

# ═══════════════════════════════════════════════════════════════════════════════
# AL-2: faq[3] — 통상임금 정의 오류 정정
# ═══════════════════════════════════════════════════════════════════════════════
faq3_old = faq[3]["answer"]
faq[3]["answer"] = (
    "연차수당 계산 시 자주 하는 실수는 기본급만으로 계산하는 것입니다. "
    "연차수당은 근로기준법 시행령 제6조의 '통상임금'을 기준으로 계산합니다. "
    "통상임금에는 기본급뿐만 아니라 직책수당·직무수당·근속수당 등 "
    "정기적이고 일률적으로 지급되는 고정 수당도 포함됩니다. "
    "반면 식비·교통비 등 실비변상 성격의 수당과 성과급(지급 조건에 따라 상이)은 "
    "통상임금에 포함되지 않는 것이 원칙입니다. "
    "기본급만으로 계산하면 실제 받아야 할 수당보다 적게 청구될 수 있으니 주의하세요."
)
print("[AL-2] faq[3] 수정")
print(f"  이전: {faq3_old[:100]}...")
print(f"  이후: {faq[3]['answer'][:100]}...")
print()

# ─── article_content 동일 오류 수정 (HTML 안 FAQ 목록) ───────────────────────
art_updated = art

# AL-3: article_content 내 "지급되지 않을 수 있습니다" 오류 정정
art_updated = art_updated.replace(
    "근로자가 연차휴가를 다 사용한 경우, 또는 사용기한이 만료된 경우에는 연차수당을 받을 수 없습니다. "
    "또한, 근로계약이 해지된 후에도 미사용 연차가 있을 경우 지급되지 않을 수 있습니다.",
    "미사용 연차수당을 받지 못하는 경우는 크게 두 가지입니다. "
    "① 해당 연도 연차를 이미 모두 사용한 경우, "
    "② 근로기준법 제61조에 따른 연차 사용 촉진제도가 적법하게 시행된 경우입니다. "
    "퇴직 시 미사용 연차수당은 원칙적으로 사용자가 지급해야 합니다(근로기준법 제36조)."
)

# AL-2: article_content 내 "기본 일급만 기준" 오류 정정
art_updated = art_updated.replace(
    "근로자들은 일급을 계산할 때 기본급 외에 수당이나 각종 복리후생비를 포함해야 한다고 오해하는 경우가 많습니다. "
    "연차수당은 기본 일급만 기준으로 하므로, 정확한 정보를 바탕으로 계산해야 합니다.",
    "연차수당 계산 시 자주 하는 실수는 기본급만으로 계산하는 것입니다. "
    "연차수당은 근로기준법 시행령 제6조의 '통상임금'을 기준으로 계산해야 하며, "
    "기본급 외에 정기적으로 지급되는 고정 수당도 포함됩니다."
)

# ── DB 저장 ───────────────────────────────────────────────────────────────────
repo.update(calc_id, {
    "faq": json.dumps(faq, ensure_ascii=False),
    "article_content": art_updated,
})
print("[DB] faq + article_content 업데이트 완료")
print()

# ─── 수정 후 전수 검색: 오류 문구 잔존 0건 확인 ───────────────────────────────
calcs2 = repo.get_all()
al2 = next((c for c in calcs2 if c.get("slug") == "annual-leave-allowance"), None)
faq2 = json.loads(al2.get("faq") or "[]")
art2 = al2.get("article_content") or ""
combined_after = " ".join(f["answer"] for f in faq2) + " " + art2

print("=" * 60)
print(" 수정 후 오류 문구 잔존 검색")
print("=" * 60)
ok = True
for v in forbidden_before:
    count = combined_after.count(v)
    status = "OK (0건)" if count == 0 else f"NG ({count}건 잔존!)"
    print(f"  '{v}': {status}")
    if count > 0:
        ok = False

print()

# ── 새 문구 포함 확인 ─────────────────────────────────────────────────────────
print("=" * 60)
print(" 수정 후 핵심 문구 포함 확인")
print("=" * 60)
checks = [
    ("통상임금", "AL-2: 통상임금 표현"),
    ("시행령 제6조", "AL-2: 시행령 조항"),
    ("고정 수당", "AL-2: 고정수당 포함 명시"),
    ("제61조", "AL-3: 제61조 촉진제도 언급"),
    ("금품 청산", "AL-3: 퇴직 시 의무 지급 근거"),
]
for phrase, label in checks:
    if phrase in combined_after:
        print(f"  [OK] {label}: '{phrase}' 포함")
    else:
        print(f"  [NG] {label}: '{phrase}' 미포함!")
        ok = False

print()
if ok:
    print(">>> 모든 검증 PASS")
else:
    print(">>> 일부 검증 실패")
    sys.exit(1)
