# -*- coding: utf-8 -*-
"""four-insurances Phase 2 콘텐츠 수정 + 이중 검증.

수정 범위:
  FI-5: 산재보험 UI 안내 추가 (article_content 주의사항)
  FI-6: faq[2] 건강보험 예시 교정 + 장기요양보험 예시 신규
  FI-7: faq[3] 고용보험 부담 비율 교정

이중 검증:
  ① 예시 금액 == compute_fi 결과 (함수 결과 인용 원칙)
  ② Total == NP + HI + LTC + EI (개별 항목 합계 일치)
"""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

# ── 계산 함수 미러 (Phase 1 로직과 동기화) ────────────────────────────────────
NP_RATE, NP_MIN, NP_MAX = 0.045, 390_000, 6_170_000
HI_RATE, LTC_RATE, EI_RATE = 0.03545, 0.1296, 0.009

def compute_fi(salary):
    np_base = min(max(salary, NP_MIN), NP_MAX)
    np  = np_base * NP_RATE
    hi  = salary * HI_RATE
    ltc = hi * LTC_RATE
    ei  = salary * EI_RATE
    tot = np + hi + ltc + ei
    return {"np": round(np), "hi": round(hi), "ltc": round(ltc),
            "ei": round(ei), "total": round(tot)}

# ── 기준값 계산 (수기 합산 금지) ─────────────────────────────────────────────
FIX = compute_fi(3_000_000)
NP, HI, LTC, EI, TOTAL = FIX["np"], FIX["hi"], FIX["ltc"], FIX["ei"], FIX["total"]

# ── 이중 검증 ────────────────────────────────────────────────────────────────
assert NP  == 135_000, f"NP fixture 오류: {NP}"
assert HI  == 106_350, f"HI fixture 오류: {HI}"
assert LTC == 13_783,  f"LTC fixture 오류: {LTC}"
assert EI  == 27_000,  f"EI fixture 오류: {EI}"
# ① 함수 결과 일치
assert TOTAL == 282_133, f"TOTAL fixture 오류: {TOTAL}"
# ② 개별 항목 합계 일치
assert NP + HI + LTC + EI == TOTAL, f"내부 합계 불일치: {NP+HI+LTC+EI} != {TOTAL}"

print(f"[기준값] NP={NP:,} / HI={HI:,} / LTC={LTC:,} / EI={EI:,} / TOTAL={TOTAL:,}")
print(f"[검증①] TOTAL == compute_fi 결과: OK")
print(f"[검증②] TOTAL == NP+HI+LTC+EI ({NP+HI+LTC+EI:,}): OK")
print()

# ── DB 로드 ────────────────────────────────────────────────────────────────
cfg  = load_config()
db   = get_db_adapter(cfg)
repo = CalculatorRepository(db)
calcs = repo.get_all()
fi = next((c for c in calcs if c.get("slug") == "four-insurances"), None)
assert fi, "four-insurances 없음"
calc_id = fi["id"]

faq = json.loads(fi.get("faq") or "[]")

# ══════════════════════════════════════════════════════════════════════════════
# FI-6: faq[2] — 건강보험 예시 교정 + 장기요양보험 신규 + total 갱신
# ══════════════════════════════════════════════════════════════════════════════
faq2_old = faq[2]["answer"]
faq[2]["answer"] = (
    f"국민연금은 월급여의 4.5%(단, 기준소득월액 하한 39만 원~상한 617만 원 범위 내 적용), "
    f"건강보험은 3.545%, 장기요양보험은 건강보험료의 12.96%, 고용보험은 0.9%를 계산하여 합산합니다. "
    f"예를 들어, 월급여가 300만 원이라면 국민연금 {NP//10000}만 {(NP%10000)//1000}천 원, "
    f"건강보험 {HI//10000}만 {(HI%10000)//1000}천 {HI%1000}백 원, "
    f"장기요양보험 {LTC//10000}만 {(LTC%10000)//1000}천 {LTC%1000}원, "
    f"고용보험 {EI//10000}만 {(EI%10000)//1000}천 원으로 합계 {TOTAL//10000}만 {(TOTAL%10000)//1000}천 {TOTAL%1000}원입니다. "
    f"산재보험은 사업주가 전액 부담하므로 근로자 급여에서 공제되지 않습니다."
)
print(f"[FI-6] faq[2] 수정")
print(f"  이전: {faq2_old[:80]}...")
print(f"  이후: {faq[2]['answer'][:80]}...")
print()

# ══════════════════════════════════════════════════════════════════════════════
# FI-7: faq[3] — 고용보험 부담 비율 교정
# ══════════════════════════════════════════════════════════════════════════════
faq3_old = faq[3]["answer"]
faq[3]["answer"] = (
    "국민연금·건강보험·장기요양보험은 근로자와 사용자가 절반씩 부담합니다. "
    "고용보험은 근로자 0.9%, 사업주 0.9%+α(규모별 추가 부담)로 정확히 절반이 아니므로 "
    "혼동하지 않도록 주의하세요. "
    "산재보험은 사업주가 전액 부담하며 근로자 급여에서 공제되지 않습니다."
)
print(f"[FI-7] faq[3] 수정")
print(f"  이전: {faq3_old[:80]}...")
print(f"  이후: {faq[3]['answer'][:80]}...")
print()

# ── faq DB 저장 ───────────────────────────────────────────────────────────
repo.update(calc_id, {"faq": json.dumps(faq, ensure_ascii=False)})
print("[DB] faq 업데이트 완료")
print()

# ══════════════════════════════════════════════════════════════════════════════
# FI-5/6/7: article_content 수정
# ══════════════════════════════════════════════════════════════════════════════
art = fi.get("article_content") or ""

# 1. 인트로 — 장기요양보험 추가
art = art.replace(
    "국민연금, 건강보험, 고용보험 등을 자동으로 계산해 드립니다.",
    "국민연금, 건강보험, 장기요양보험, 고용보험을 자동으로 계산해 드립니다."
)

# 2. 결과 항목 — 장기요양보험 행 추가 (고용보험 앞에 삽입)
art = art.replace(
    "    <li>고용보험: <span id=\"employment_insurance\">0</span> 원</li>",
    "    <li>장기요양보험: <span id=\"long_term_care\">0</span> 원</li>\n    <li>고용보험: <span id=\"employment_insurance\">0</span> 원</li>"
)

# 3. 계산 원리 — 건강보험 예시 교정
art = art.replace(
    "건강보험은 월급여의 3.545%입니다. 같은 사례에서 300만 원의 3.545%는 300만 원 × 0.03545 = 10만 6천 500원이 됩니다.",
    f"건강보험은 월급여의 3.545%입니다. 같은 사례에서 300만 원의 3.545%는 300만 원 × 0.03545 = {HI//10000}만 {(HI%10000)//1000}천 {HI%1000}원이 됩니다."
)

# 4. 계산 원리 — 장기요양보험 항목 추가 (고용보험 항목 앞에 삽입)
art = art.replace(
    "    <li>고용보험은 월급여의 0.9%로,",
    f"    <li>장기요양보험은 건강보험료의 12.96%입니다. 같은 사례에서 건강보험료({HI//10000}만 {(HI%10000)//1000}천 {HI%1000}원) × 12.96% = {LTC//10000}만 {(LTC%10000)//1000}천 {LTC%1000}원이 됩니다.</li>\n    <li>고용보험은 월급여의 0.9%로,"
)

# 5. 계산 원리 — 총 합계 교정 (구 수치 → 함수 결과)
art = art.replace(
    "이 모든 금액을 합하면, 총 보험료는 13만 5천 원 + 10만 6천 500원 + 2만 7천 원 = 26만 8천 500원이 됩니다.",
    f"이 모든 금액을 합하면, 총 보험료는 {NP//10000}만 {(NP%10000)//1000}천 원 + {HI//10000}만 {(HI%10000)//1000}천 {HI%1000}원 + {LTC//10000}만 {(LTC%10000)//1000}천 {LTC%1000}원 + {EI//10000}만 {(EI%10000)//1000}천 원 = {TOTAL//10000}만 {(TOTAL%10000)//1000}천 {TOTAL%1000}원이 됩니다. (산재보험은 사업주 전액 부담으로 미포함)"
)

# 6. 주의사항 — 산재보험 안내 추가 (FI-5)
art = art.replace(
    "    <li>사용자와 근로자가 각각 일부를 부담하기 때문에 이 부분도 고려해야 합니다.</li>",
    "    <li>고용보험은 근로자 0.9%, 사업주 0.9%+α(규모별 추가)로 부담 비율이 다릅니다.</li>\n    <li><strong>산재보험은 사업주가 전액 부담합니다</strong> — 근로자 급여에서 공제되지 않으며 계산기에 표시되지 않습니다 (산업재해보상보험법 제13조).</li>"
)

# 7. FAQ — article_content 내 계산 설명 교정
art = art.replace(
    "    <dd>국민연금은 월급여의 4.5%, 건강보험은 3.545%, 고용보험은 0.9%로 계산하여 총합산합니다.</dd>",
    f"    <dd>국민연금 4.5%(기준소득월액 상한·하한 적용), 건강보험 3.545%, 장기요양보험(건강보험료 × 12.96%), 고용보험 0.9%를 계산하여 합산합니다. 월급여 300만 원 기준 합계 {TOTAL//10000}만 {(TOTAL%10000)//1000}천 {TOTAL%1000}원.</dd>"
)

repo.update(calc_id, {"article_content": art})
print("[DB] article_content 업데이트 완료")
print()

# ══════════════════════════════════════════════════════════════════════════════
# 이중 검증 최종: 오류 수치 잔존 0건 확인
# ══════════════════════════════════════════════════════════════════════════════
print("="*60)
print(" 이중 검증 최종")
print("="*60)

# DB 재로드
calcs2 = repo.get_all()
fi2 = next((c for c in calcs2 if c.get("slug") == "four-insurances"), None)
faq2_list = json.loads(fi2.get("faq") or "[]")
art2 = fi2.get("article_content") or ""
combined = " ".join(f["answer"] for f in faq2_list) + " " + art2

# ── 구 오류 수치 잔존 검사 ───────────────────────────────────────────────────
forbidden_numbers = [
    ("106,500", "건강보험 구 예시(FI-6 교정 전)"),
    ("106500",  "건강보험 구 예시(FI-6 교정 전)"),
    ("10만 6천 500", "건강보험 구 예시(FI-6 교정 전)"),
    ("268,500", "장기요양 누락 구 total(FI-3 교정 전)"),
    ("268500",  "장기요양 누락 구 total(FI-3 교정 전)"),
    ("26만 8천 500", "장기요양 누락 구 total(FI-3 교정 전)"),
    ("각 보험료는 근로자와 사용자가 절반씩 부담", "고용보험 부담 비율 일반화 오류(FI-7 교정 전)"),
]
ok = True
for val, label in forbidden_numbers:
    if val in combined:
        print(f"[NG] 구 오류 수치 잔존: '{val}' ({label})")
        ok = False
    else:
        print(f"[OK] '{val}' 잔존 없음")

print()

# ── ① 예시 금액 == 함수 결과 검증 ────────────────────────────────────────────
checks = [
    (f"{NP//10000}만 {(NP%10000)//1000}천", "국민연금 13만 5천"),
    (f"{HI//10000}만 {(HI%10000)//1000}천 {HI%1000}", "건강보험 10만 6천 350"),
    (f"{LTC//10000}만 {(LTC%10000)//1000}천 {LTC%1000}", "장기요양 1만 3천 783"),
    (f"{EI//10000}만 {(EI%10000)//1000}천", "고용보험 2만 7천"),
    (f"{TOTAL//10000}만 {(TOTAL%10000)//1000}천 {TOTAL%1000}", "합계 28만 2천 133"),
]
for val, label in checks:
    if val in combined:
        print(f"[검증①] {label}: 함수 결과 인용 OK")
    else:
        print(f"[검증①] {label}: 미발견! (val={val!r})")
        ok = False

print()

# ── ② total == 개별 합계 검증 (compute_fi 수준) ─────────────────────────────
sum_items = NP + HI + LTC + EI
assert sum_items == TOTAL, f"개별 합계 불일치: {sum_items} != {TOTAL}"
print(f"[검증②] TOTAL({TOTAL:,}) == NP+HI+LTC+EI ({sum_items:,}): OK")

print()
if ok:
    print(">>> 모든 검증 PASS")
else:
    print(">>> 일부 검증 실패 — 위 NG 항목 확인 필요")
    sys.exit(1)
