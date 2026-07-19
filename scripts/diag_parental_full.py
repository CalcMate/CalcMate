# -*- coding: utf-8 -*-
"""육아휴직급여 계산기 전수 진단."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

cfg = load_config()
db = get_db_adapter(cfg)
repo = CalculatorRepository(db)
calcs = repo.get_all()
pl = next((c for c in calcs if c.get("slug") == "육아휴직_급여_계산기"), None)
assert pl, "계산기 없음"

faq = json.loads(pl.get("faq") or "[]")
art = pl.get("article_content") or ""
combined = " ".join(f["answer"] for f in faq) + " " + art

# ── 1. 입력 스키마 ─────────────────────────────────────────────────────────────
print("=" * 60)
print(" 1. 입력/출력 스키마")
print("=" * 60)
inputs_raw = pl.get("inputs")
inputs_list = json.loads(inputs_raw) if isinstance(inputs_raw, str) else (inputs_raw or [])
print(f"inputs ({len(inputs_list)}개):")
for inp in inputs_list:
    print(f"  {inp}")

outputs_raw = pl.get("outputs")
outputs_list = json.loads(outputs_raw) if isinstance(outputs_raw, str) else (outputs_raw or [])
print(f"outputs ({len(outputs_list)}개):")
for o in outputs_list:
    print(f"  {o}")
print(f"formula_engine: {len(pl.get('formula_engine') or '')}자 (비어있음={not pl.get('formula_engine')})")
print()

# ── 2. 현재 계산식 vs 법령 기준 (2026년 기준) ──────────────────────────────────
print("=" * 60)
print(" 2. 현재 계산식 vs 법령 기준 대조")
print("=" * 60)

# 현재 계산식 재현 (script.js에서 추출)
def compute_current(avg_monthly_wage, leave_months, gov_pct, company_pct):
    return ((avg_monthly_wage * leave_months) * ((gov_pct + company_pct) / 100))

# 법령 기준 계산식 (고용보험법 시행령 제95조, 2024년 기준)
# 일반 육아휴직급여: 통상임금 × 80%, 상한 150만, 하한 70만
# 6+6 특례 (2024년 1월 시행): 부모 모두 육아휴직 시 첫 6개월 100%, 단계별 상한
PL_RATE_GENERAL = 0.80
PL_CAP_GENERAL  = 1_500_000   # 월 상한 150만원
PL_FLOOR        = 700_000     # 월 하한 70만원

# 6+6 특례 상한 (월별)
PL_66_CAP = {1: 2_000_000, 2: 2_500_000, 3: 3_000_000,
             4: 3_500_000, 5: 4_000_000, 6: 4_500_000}

def compute_correct_general(monthly_wage, months=1):
    """일반 육아휴직급여 1개월분."""
    raw = monthly_wage * PL_RATE_GENERAL
    clamped = min(max(raw, PL_FLOOR), PL_CAP_GENERAL)
    return clamped

def compute_correct_66(monthly_wage, month_idx):
    """6+6 특례 1개월분 (month_idx: 1~6)."""
    raw = monthly_wage * 1.0  # 100%
    cap = PL_66_CAP.get(month_idx, PL_CAP_GENERAL)
    return min(raw, cap)

print("[케이스 A] 통상임금 300만원, 일반 육아휴직 1개월")
w = 3_000_000
cur = compute_current(w, 1, 80, 0)
cor = compute_correct_general(w)
print(f"  현재 계산 (80% 입력 가정): {cur:,.0f}원")
print(f"  법령 기준 (80%, 상한 150만): {cor:,.0f}원")
print(f"  → {'일치' if abs(cur-cor)<1 else '불일치'} (현재 계산기는 상한/하한 없음)")
print()

print("[케이스 B] 통상임금 80만원, 일반 육아휴직 (하한 적용)")
w = 800_000
cur = compute_current(w, 1, 80, 0)
cor = compute_correct_general(w)
print(f"  현재 계산: {cur:,.0f}원")
print(f"  법령 기준 (80%=64만 → 하한 70만 적용): {cor:,.0f}원")
print(f"  → {'일치' if abs(cur-cor)<1 else '불일치'}")
print()

print("[케이스 C] 통상임금 200만원, 6+6 특례 1개월")
w = 2_000_000
cur = compute_current(w, 1, 100, 0)
cor = compute_correct_66(w, 1)
print(f"  현재 계산 (100% 입력 가정): {cur:,.0f}원")
print(f"  법령 기준 (100%, 상한 200만): {cor:,.0f}원")
print(f"  → {'일치' if abs(cur-cor)<1 else '불일치'} (현재 계산기는 특례 상한 없음)")
print()

print("[케이스 D] 통상임금 500만원, 6+6 특례 6개월")
w = 5_000_000
cur = compute_current(w, 1, 100, 0)
cor = compute_correct_66(w, 6)
print(f"  현재 계산: {cur:,.0f}원")
print(f"  법령 기준 (100%, 상한 450만): {cor:,.0f}원")
print(f"  → {'일치' if abs(cur-cor)<1 else '불일치'}")
print()

# ── 3. 지급률 구간 계단 구조 (법령 기준) ──────────────────────────────────────
print("=" * 60)
print(" 3. 지급률 구간 계단 구조 (법령 기준 2024년 시행)")
print("=" * 60)
print("[ 일반 육아휴직급여 ]")
print(f"  전 기간(1~12개월): 통상임금 × {PL_RATE_GENERAL*100:.0f}%")
print(f"  상한: {PL_CAP_GENERAL:,}원/월, 하한: {PL_FLOOR:,}원/월")
print()
print("[ 6+6 부모 육아휴직 특례 (2024년 1월 시행, 생후 18개월 이내) ]")
print("  조건: 부모 모두 육아휴직 (각자 최초 1회씩 사용)")
print("  ┌─────┬──────────┬──────────────┐")
print("  │ 월  │ 지급률   │ 월 상한      │")
print("  ├─────┼──────────┼──────────────┤")
for m, cap in PL_66_CAP.items():
    print(f"  │ {m:2d}월 │  100%    │ {cap//10000:>4d}만원      │")
print("  ├─────┼──────────┼──────────────┤")
print("  │7~12│   80%    │  150만원      │  ← 일반 전환")
print("  └─────┴──────────┴──────────────┘")
print()

# ── 4. 법령 재검증 — 제70조 + forbidden_articles ──────────────────────────────
print("=" * 60)
print(" 4. 법령 재검증 + forbidden_articles 전수 검색")
print("=" * 60)

print("[제70조 대응 확인]")
print("  고용보험법 제70조①: 30일 이상 육아휴직, 피보험단위기간 180일 이상 → 급여 지급")
has_70 = "제70조" in combined
has_180 = "180일" in combined or "피보험단위기간" in combined
print(f"  FAQ/article에 제70조 언급: {has_70}")
print(f"  FAQ/article에 180일/피보험단위기간 언급: {has_180}")
print()

print("[forbidden_articles 전수 검색]")
forbidden = ["고용보험법 제40조", "근로기준법 제74조"]
for art_phrase in forbidden:
    count = combined.count(art_phrase)
    status = "OK (0건)" if count == 0 else f"NG ({count}건 발견!)"
    print(f"  [{status}] '{art_phrase}'")
print()

# ── 5. C-13 원칙-예외 구조 검증 ───────────────────────────────────────────────
print("=" * 60)
print(" 5. C-13 원칙-예외 구조 (지급 원칙 vs 미지급 요건)")
print("=" * 60)
PRINCIPLE_PHRASES = ["180일", "피보험단위기간"]
EXCEPTION_PHRASES = ["제70조", "고용보험법"]

faq1 = faq[1]["answer"] if len(faq) > 1 else ""
has_principle_faq = any(p in faq1 for p in PRINCIPLE_PHRASES)
has_principle_art = any(p in art for p in PRINCIPLE_PHRASES)
print(f"  FAQ[1] 핵심 요건(180일 피보험단위기간) 언급: {has_principle_faq}")
print(f"  article_content 핵심 요건 언급: {has_principle_art}")

# 자녀 연령 요건
faq0 = faq[0]["answer"] if len(faq) > 0 else ""
has_age_error = "출산 후 1년" in faq0
has_age_correct = "8세" in combined or "초등학교 2학년" in combined
print(f"  FAQ[0] '출산 후 1년' 오류 표현 존재: {has_age_error} (현행: 8세 이하)")
print(f"  '8세 이하' 또는 '초등학교 2학년' 언급: {has_age_correct}")
print()

# ── 6. 입력 검증 확인 ─────────────────────────────────────────────────────────
print("=" * 60)
print(" 6. 입력 검증 (AL-1/B-2 패턴 적용 여부)")
print("=" * 60)
# script.js 내용 확인
import pathlib
script_path = pathlib.Path(__file__).resolve().parent.parent / "data" / "workspace" / "육아휴직_급여_계산기" / "script.js"
script_js = script_path.read_text(encoding="utf-8")
has_null_check = "return null" in script_js
has_negative_check = "<= 0" in script_js or "< 0" in script_js
print(f"  null 반환 처리: {has_null_check}")
print(f"  음수/0 검증: {has_negative_check}")

has_notices = "notices" in script_js
has_formula = "_formula" in script_js
print(f"  notices 구현: {has_notices}")
print(f"  _formula 구현: {has_formula}")
print()

# ── 7. SP-8 유사 — 코드 문자열 노출 확인 ─────────────────────────────────────
print("=" * 60)
print(" 7. SP-8 유사 — 코드 문자열 노출 확인")
print("=" * 60)
code_strings = [
    "avg_monthly_wage",
    "government_support_percentage",
    "company_policy_support_percentage",
    "leave_months",
]
for cs in code_strings:
    count = combined.count(cs)
    status = "NG (노출)" if count > 0 else "OK"
    print(f"  [{status}] '{cs}': {count}건")
print()

# ── 8. 특례 우선순위 확인 ─────────────────────────────────────────────────────
print("=" * 60)
print(" 8. 특례 우선순위 (6+6 특례 구현 여부)")
print("=" * 60)
has_66 = "6+6" in script_js or "66" in script_js
has_33 = "3+3" in script_js or "33" in script_js
has_special = "특례" in script_js
print(f"  6+6 특례 구현: {has_66}")
print(f"  3+3 특례 구현: {has_33}")
print(f"  특례 로직 존재: {has_special}")
print(f"  현재 단일 공식: True (특례 없음)")
print()

# ── 9. 경계값 (법령 기준 계산) ────────────────────────────────────────────────
print("=" * 60)
print(" 9. 경계값 테스트 (법령 기준)")
print("=" * 60)
boundary_cases = [
    (875_000, "하한 경계 (87.5만 × 80% = 70만)"),
    (876_000, "하한 초과 (87.6만 × 80% = 70.08만)"),
    (1_875_000, "상한 경계 (187.5만 × 80% = 150만)"),
    (1_876_000, "상한 초과 (187.6만 × 80% = 150.08만 → 150만 cap)"),
    (2_000_000, "6+6 1개월 (200만 × 100% = 200만 = 상한)"),
    (2_000_001, "6+6 1개월 초과 (200만+1 → 200만 cap)"),
    (4_500_000, "6+6 6개월 (450만 × 100% = 450만 = 상한)"),
]
print("  통상임금 → 일반 급여 → 6+6 1개월 → 6+6 6개월")
print()
for w, label in boundary_cases:
    gen = compute_correct_general(w)
    s66_1 = compute_correct_66(w, 1)
    s66_6 = compute_correct_66(w, 6)
    print(f"  {w:>10,}원 | 일반: {gen:>9,}원 | 6+6-1: {s66_1:>9,}원 | 6+6-6: {s66_6:>9,}원")
    print(f"    ({label})")
print()

# ── 10. 기준연도 하드코딩 확인 ──────────────────────────────────────────────────
print("=" * 60)
print(" 10. 기준연도 / 상한·하한 하드코딩 확인")
print("=" * 60)
amounts_in_js = []
import re
for m in re.findall(r'\d{3,}', script_js):
    v = int(m)
    if v > 100000:
        amounts_in_js.append(v)
print(f"  JS 내 큰 수치(>10만): {amounts_in_js}")
print(f"  법령 상한(150만)·하한(70만) 하드코딩: {1500000 in amounts_in_js or 700000 in amounts_in_js}")
print()

# ── 11. FAQ/content 핵심 오류 요약 ────────────────────────────────────────────
print("=" * 60)
print(" 11. FAQ 핵심 오류 목록")
print("=" * 60)
errors = []

# FAQ[0] 자녀 연령
if "출산 후 1년" in faq[0]["answer"]:
    errors.append(("[0] Critical", "자녀 연령: '출산 후 1년 이내' → 현행 만 8세 이하(초등 2학년 이하)"))

# FAQ[1] 핵심 요건 누락
if "180일" not in faq[1]["answer"] and "피보험단위기간" not in faq[1]["answer"]:
    errors.append(("[1] Critical", "핵심 수급 요건(180일 피보험단위기간) 미언급"))
if "최저임금" in faq[1]["answer"]:
    errors.append(("[1] Major", "'최저임금 미충족' → 수급 제외 요건이 아님"))

# FAQ[2] 계산식 오류
if "government_support_percentage" in faq[2]["answer"] or "회사 정책지원 비율" in faq[2]["answer"]:
    errors.append(("[2] Critical", "계산식 코드 문자열 노출 + 법령과 무관한 계산 구조 서술"))

# FAQ[6] 육아휴직 1년 권리
if "회사의 정책에 따라" in faq[6]["answer"]:
    errors.append(("[6] Critical", "육아휴직 1년은 법적 권리(남녀고용평등법 제19조) — '회사 정책에 따라' 오류"))

# FAQ[7] 복귀 의사 사전 표명
if "근무 복귀 의사를 사전에" in faq[7]["answer"]:
    errors.append(("[7] Major", "'복귀 의사 사전 표명' — 법적 요건 아님"))

# 계산식 근본 오류
errors.append(("[JS] Critical", "computeResult 계산식 근본 오류 — 지급률 사용자 입력 구조, 상한/하한 없음, 특례 없음"))
errors.append(("[설계] Critical", "입력 구조 오류 — government_support_percentage, company_policy_support_percentage는 법령 고정값"))

for code, desc in errors:
    print(f"  {code}: {desc}")
print()

print(f"총 발견 오류: {len(errors)}건")
print()
print(">>> 진단 완료")
