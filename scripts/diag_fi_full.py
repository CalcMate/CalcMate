# -*- coding: utf-8 -*-
"""four-insurances 10개 항목 전수 진단"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

cfg = load_config()
db = get_db_adapter(cfg)
repo = CalculatorRepository(db)
fi = next((c for c in repo.get_all() if c.get("slug") == "four-insurances"), None)

formula = json.loads(fi.get("formula") or "{}")

# ── 현행 요율 (2025년 기준, 학습 데이터 기준 — 매년 확인 필요) ──────────────
NP_RATE     = 0.045          # 국민연금 근로자 4.5%
HI_RATE     = 0.03545        # 건강보험 근로자 3.545% (2025년)
LTC_RATE    = 0.1296         # 장기요양보험 = 건강보험료 × 12.96% (2025년)
EI_RATE     = 0.009          # 고용보험 근로자 0.9%
NP_MIN      = 390_000        # 국민연금 기준소득월액 하한 (2024.7~2025.6)
NP_MAX      = 6_170_000      # 국민연금 기준소득월액 상한 (2024.7~2025.6)

def compute_current(salary):
    """현재 코드 그대로"""
    out = {}
    out["national_pension"] = salary * 0.045
    out["health_insurance"] = salary * 0.03545
    out["employment_insurance"] = salary * 0.009
    out["total"] = salary * (0.045 + 0.03545 + 0.009)
    return out

def compute_correct(salary):
    """올바른 계산 (상한/하한 + 장기요양)"""
    if salary <= 0:
        return None
    np_base = min(max(salary, NP_MIN), NP_MAX)
    np = np_base * NP_RATE
    hi = salary * HI_RATE
    ltc = hi * LTC_RATE
    ei = salary * EI_RATE
    return {
        "national_pension": np,
        "health_insurance": hi,
        "long_term_care": ltc,
        "employment_insurance": ei,
        "total": np + hi + ltc + ei,
    }

# ── 비교 케이스 ────────────────────────────────────────────────────────────────
print("="*72)
print(" four-insurances 현재 코드 vs 올바른 계산 비교")
print("="*72)

cases = [
    (200_000, "하한 미만 (20만원)"),
    (390_000, "하한 경계 (39만원)"),
    (400_000, "하한 직후 (40만원)"),
    (3_000_000, "정상 (300만원)"),
    (6_170_000, "상한 경계 (617만원)"),
    (6_200_000, "상한 직후 (620만원)"),
    (10_000_000, "상한 초과 (1000만원)"),
]

for salary, desc in cases:
    cur = compute_current(salary)
    cor = compute_correct(salary)
    np_err = abs(cur["national_pension"] - cor["national_pension"])
    total_cur = cur["total"]
    total_cor = cor["total"]
    total_err = total_cur - total_cor  # 현재 - 올바른 (양수 = 과소 계산, 음수 = 과다)
    print(f"\n[{desc}]  salary={salary:,}원")
    print(f"  현재: NP={cur['national_pension']:,.0f}  HI={cur['health_insurance']:,.0f}  LTC=없음  EI={cur['employment_insurance']:,.0f}  total={total_cur:,.0f}")
    print(f"  올바: NP={cor['national_pension']:,.0f}  HI={cor['health_insurance']:,.0f}  LTC={cor['long_term_care']:,.0f}  EI={cor['employment_insurance']:,.0f}  total={total_cor:,.0f}")
    issues = []
    if np_err > 1:
        issues.append(f"NP오차={np_err:,.0f}원(상한/하한 미적용)")
    if cor.get("long_term_care", 0) > 0:
        issues.append(f"LTC누락={cor['long_term_care']:,.0f}원")
    if issues:
        print(f"  오류: {' | '.join(issues)}")

# ── formula 확인 ───────────────────────────────────────────────────────────────
print("\n" + "="*72)
print(" DB formula 확인")
print("="*72)
print(json.dumps(formula, ensure_ascii=False, indent=2))

# ── 장기요양보험 계산 순서 확인 ─────────────────────────────────────────────
print("\n" + "="*72)
print(" FI-1: 장기요양보험 계산 순서 검증")
print("="*72)
salary = 3_000_000
hi = salary * HI_RATE
ltc_correct = hi * LTC_RATE          # 건강보험료에 장기요양률 곱셈
ltc_wrong   = salary * LTC_RATE      # 급여에 직접 곱하는 오류
print(f"  월급여={salary:,}원  건강보험료={hi:,.0f}원")
print(f"  올바른 순서: 건강보험료({hi:,.0f}) × {LTC_RATE} = {ltc_correct:,.0f}원")
print(f"  잘못된 순서: 급여({salary:,}) × {LTC_RATE} = {ltc_wrong:,.0f}원  (오차={ltc_wrong-ltc_correct:,.0f}원)")
print(f"  현재 코드: 장기요양보험 변수 자체 없음 → 미구현")

# ── 국민연금 경계값 3점 세트 ─────────────────────────────────────────────────
print("\n" + "="*72)
print(" FI-2: 국민연금 기준소득월액 경계값 3점 세트")
print("="*72)
for boundary, label in [(NP_MIN-1,"하한-1"), (NP_MIN,"하한"), (NP_MIN+1,"하한+1"),
                         (NP_MAX-1,"상한-1"), (NP_MAX,"상한"), (NP_MAX+1,"상한+1")]:
    cur_np = boundary * 0.045
    correct_np = min(max(boundary, NP_MIN), NP_MAX) * 0.045
    diff = cur_np - correct_np
    ok = abs(diff) < 1
    print(f"  [{label}={boundary:,}원]  현재={cur_np:,.0f}  올바={correct_np:,.0f}  차이={diff:+,.0f}  {'OK' if ok else 'NG'}")

# ── FAQ 예시 계산 검증 ──────────────────────────────────────────────────────
print("\n" + "="*72)
print(" FI-SEO: faq[2] 예시 금액 검증 (월 300만원)")
print("="*72)
s = 3_000_000
print(f"  국민연금: {s:,} × 4.5% = {s*0.045:,.0f}원  (faq: 13만 5천 원 = 135,000원  {'OK' if abs(s*0.045-135000)<1 else 'NG'})")
print(f"  건강보험: {s:,} × 3.545% = {s*0.03545:,.0f}원  (faq: 10만 6천 500원 = 106,500원  {'OK' if abs(s*0.03545-106500)<1 else 'NG'})")
print(f"  고용보험: {s:,} × 0.9% = {s*0.009:,.0f}원  (faq: 2만 7천 원 = 27,000원  {'OK' if abs(s*0.009-27000)<1 else 'NG'})")
print(f"  faq 합계: 135,000 + 106,500 + 27,000 = 268,500원  (장기요양 누락)")
print(f"  실제 합계: {compute_correct(s)['total']:,.0f}원")

# ── 결과 요약 ────────────────────────────────────────────────────────────────
print("\n" + "="*72)
print(" 진단 결과 요약")
print("="*72)
issues = [
    ("FI-1", "Critical", "장기요양보험 미구현 — 전체 보험료 합계 과소(월300만원: ~13,790원 누락)"),
    ("FI-2", "Critical", "국민연금 기준소득월액 상한/하한 클램프 없음 (상한 초과 시 최대 17.2만원 오차)"),
    ("FI-3", "Critical", "total 출력에 장기요양보험 미포함"),
    ("FI-4", "Major",    "입력 검증 없음 (monthly_salary<=0 → 0/음수 결과, no null 반환)"),
    ("FI-5", "Major",    "산재보험 UI 안내 없음 — '4대보험' 표제인데 산재보험 설명 부재"),
    ("FI-6", "Major",    "faq[2] 건강보험 예시금액 오류: 106,500원(×) → 106,350원(○)"),
    ("FI-7", "Major",    "faq[3] 고용보험 '절반씩 부담' 오류 — 고용보험은 근로자:사업주=0.9%:1.65%"),
    ("FI-8", "Minor",    "_formula 미구현 (계산 과정 미표시)"),
    ("FI-9", "Minor",    "notices 배열 없음 (상한/하한 클램프 적용 안내 없음)"),
    ("FI-10","Minor",    "요율/기준액 하드코딩 — legal_basis 외부화 미적용 (매년 갱신 필요)"),
]
for num, sev, desc in issues:
    print(f"  [{num}] [{sev:8s}] {desc}")
