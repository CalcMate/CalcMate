# -*- coding: utf-8 -*-
"""실업급여 계산기 전수 검증 (10개 항목)

항목:
  1. 입력값 검증
  2. 계산식 검증 (고용보험법 기준 대조)
  3. 설계 범위 확정
  4. 예외 케이스
  5. 반올림 방식
  6. 정부 기준 대조 3건
  7. 경계값/소정급여일수 테이블 대조
  8. 기준연도 확인
  9. UI 결과 / forbidden_articles 확인
  10. SEO 글 대조
"""
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
calc = next((c for c in calcs if c.get("slug") == "unemployment-benefit"), None)

def sep(title):
    print(f"\n{'='*70}\n {title}\n{'='*70}")

# ──────────────────────────────────────────────────────────────────────
# 기준 데이터 (고용보험법 별표1 소정급여일수 — 재검증 필요)
# ──────────────────────────────────────────────────────────────────────
# 가입기간 구간: [미만 개월수, 상한 개월수) → 일수
# 50세 미만
TABLE_UNDER50 = [
    (0,   12,  120),   # 1년 미만
    (12,  36,  150),   # 1년~3년 미만
    (36,  60,  180),   # 3년~5년 미만
    (60,  120, 210),   # 5년~10년 미만
    (120, None, 240),  # 10년 이상
]
# 50세 이상 및 장애인
TABLE_50PLUS = [
    (0,   12,  120),
    (12,  36,  180),
    (36,  60,  210),
    (60,  120, 240),
    (120, None, 270),
]

def get_benefit_days(age, months):
    table = TABLE_50PLUS if age >= 50 else TABLE_UNDER50
    for lo, hi, days in table:
        if hi is None or months < hi:
            if months >= lo:
                return days
    return None

# 상한/하한 (2025~2026년 기준, 고용부 고시 — 재검증 필요)
# 상한액: 66,000원/일 (2024년 이후 동일)
# 하한액: 최저임금(10,030원) × 8시간 × 80% = 64,192원
DAILY_MAX = 66_000
DAILY_MIN = round(10_030 * 8 * 0.8)  # 64,192

def code_compute(avg_daily_wage):
    """현재 코드의 computeResult 로직"""
    return avg_daily_wage * 0.6

def law_compute(avg_daily_wage, apply_cap=True):
    """법령 기준 기초일액 (상한/하한 적용)"""
    base = avg_daily_wage * 0.6
    if apply_cap:
        return max(DAILY_MIN, min(DAILY_MAX, base))
    return base

# ══════════════════════════════════════════════════════════════════════
sep("1. 입력값 검증")
print("""
코드 입력: avg_daily_wage (number), age (number), employment_months (number)
compute_rules: 없음 → 양수 검증 없음

문제 항목:
  UB-1a [major] avg_daily_wage <= 0 입력 시 null 미반환 (0 또는 음수 결과 표시)
  UB-1b [minor] age <= 0 또는 employment_months <= 0 입력 시 처리 없음
  기존 패턴: SP-3/SP-4 방식 재사용 가능 (positive_inputs 또는 date_based 분기 로직)
""")

# ══════════════════════════════════════════════════════════════════════
sep("2. 계산식 검증 — 고용보험법 기준 대조")
print(f"""
현재 코드: daily_benefit = avg_daily_wage * 0.6

고용보험법 제46조 (구직급여액):
  기초일액 = 기준기간(3개월) 중 피보험자의 임금 총액 ÷ 기준기간 일수
  구직급여 일액 = 기초일액 × 60/100
  상한: 66,000원/일 (고용부 고시, 2024년 이후)
  하한: 최저임금 × 80% (일 기준) = {DAILY_MIN:,}원/일 (2026년 기준 추정)

코드 vs 법령:
  [OK ] 60% 비율 자체는 법령 기준과 일치
  [NG ] 상한액({DAILY_MAX:,}원) 미적용 → avg_daily_wage > {round(DAILY_MAX/0.6):,}원 시 과대 계산
  [NG ] 하한액({DAILY_MIN:,}원) 미적용 → avg_daily_wage < {round(DAILY_MIN/0.6):,}원 시 과소 계산
  [NG ] 소정급여일수 테이블 미적용 (age, employment_months 전혀 사용 안 함)
  [NG ] total_benefit output_schema에 있지만 computeResult가 반환 안 함
""")

# ══════════════════════════════════════════════════════════════════════
sep("3. 설계 범위 확정")
print("""
legal_basis.draft.yaml 명시:
  "요건(180일·수급자격)은 계산기가 산출하지 않고 급여액만 계산"
  compute_type: single
  difficulty: complex, difficulty_status: provisional

결과 카드 레이블: "예상 1일 구직급여"

설계 범위: 예상 일 구직급여 계산기 (수급자격 판정 미포함)
  - 이직사유별 수급 가능 여부 반영: 설계 범위 외 (버그 아님)
  - 180일 미만 수급자격 미충족 안내: 설계 범위 외이나, 사용자 혼란 방지를 위해 notice 추가 고려
  - 소정급여일수 계산: 현재 미구현이나 입력이 존재함 → 기능 불완전 (UB-3)
  - total_benefit 반환 미구현: 코드 누락 (UB-4)

판단: 수급자격 판정은 설계 범위 외. 그러나 age+employment_months를 입력받고
      소정급여일수를 계산에 반영하지 않는 것은 UX 기만 — 사용자가 입력하는 값이
      무시된다는 것을 알 방법이 없음. 이것은 버그이거나 미구현 기능.
""")

# ══════════════════════════════════════════════════════════════════════
sep("4. 예외 케이스")
print(f"""
4-1. 180일 미만 (설계 범위 외 + UX 고려):
  employment_months < 6 시 수급자격 미충족 (피보험단위기간 180일 = 약 6개월)
  현재: 처리 없음 (그냥 daily_benefit 계산 반환)
  권장: notice 추가 ("고용보험 가입기간이 180일 미만이면 수급 자격이 없을 수 있습니다")
  단, 설계 범위 외이므로 notice 삽입 여부는 수정 결정 시 판단

4-2. 기초일액 산정 방식:
  현재: avg_daily_wage = 입력값 그대로 (평균 일임금을 직접 입력)
  법령: 기초일액 = (퇴직 전 3개월 임금 총액) ÷ (3개월 총일수)
  설계 범위: 단순 계산기 (사용자가 직접 입력) — 퇴직금 계산기와 동일 패턴
  문제: 입력 레이블 "평균 일임금"이 기초일액과 동일하므로 설계상 합리적

4-3. 상한/하한 경계:
  avg_daily_wage > {round(DAILY_MAX/0.6):,}원 → daily_benefit이 상한 {DAILY_MAX:,}원 초과해야 함
  avg_daily_wage < {round(DAILY_MIN/0.6):,}원 → daily_benefit이 하한 {DAILY_MIN:,}원 미만 → 하한 적용해야 함
  현재: 두 경우 모두 처리 없음
""")

# ══════════════════════════════════════════════════════════════════════
sep("5. 반올림 방식")
print("""
현재 코드: avg_daily_wage * 0.6 (Math.round 없음 → 소수점 그대로 반환)
UI: renderResult()의 comma() = Math.round(n).toLocaleString()
     → 표시는 반올림되지만 내부값은 소수점 유지

법령 기준: 원 미만 절사 (고용보험법 — 일반적으로 원 단위 절사)

문제: 법령은 원 미만 절사이나 Math.round는 반올림 → 미세 차이 가능
      minor severity (표시에서 ±1원 이내)
""")

# ══════════════════════════════════════════════════════════════════════
sep("6. 정부 기준 대조 3건 비교")
print(f"""
고용보험법 기준 (상한 {DAILY_MAX:,}원, 하한 {DAILY_MIN:,}원 적용, 소정급여일수 별표1)

케이스 1. 일반 (35세, 24개월, 평균일급 100,000원)
  기초일액 = 100,000 × 0.6 = 60,000원
  하한 적용 → {DAILY_MIN:,}원/일 (법령)
  현재 코드 → 60,000원/일 (하한 미적용 → 과소 {DAILY_MIN-60000:,}원)
  소정급여일수 = {get_benefit_days(35,24)}일 (50세 미만, 1~3년)
  법령 총 구직급여 = {DAILY_MIN:,} × {get_benefit_days(35,24)} = {DAILY_MIN*get_benefit_days(35,24):,}원
  코드 총액 = 60,000 × {get_benefit_days(35,24)} = {60000*get_benefit_days(35,24):,}원 (소정일수 미계산)

케이스 2. 상한액 (45세, 5년, 평균일급 150,000원)
  기초일액 = 150,000 × 0.6 = 90,000원
  상한 적용 → {DAILY_MAX:,}원/일 (법령)
  현재 코드 → 90,000원/일 (상한 미적용 → 과대 {90000-DAILY_MAX:,}원)
  소정급여일수 = {get_benefit_days(45,60)}일 (50세 미만, 5~10년)
  법령 총 구직급여 = {DAILY_MAX:,} × {get_benefit_days(45,60)} = {DAILY_MAX*get_benefit_days(45,60):,}원
  코드 총액 = 90,000 × {get_benefit_days(45,60)} = {90000*get_benefit_days(45,60):,}원 (소정일수 미계산)

케이스 3. 경계 하한 (25세, 6개월, 평균일급 70,000원)
  기초일액 = 70,000 × 0.6 = 42,000원
  하한 적용 → {DAILY_MIN:,}원/일 (법령)
  현재 코드 → 42,000원/일 (하한 미적용 → 과소 {DAILY_MIN-42000:,}원)
  소정급여일수 = {get_benefit_days(25,6)}일 (50세 미만, 1년 미만)
  법령 총 구직급여 = {DAILY_MIN:,} × {get_benefit_days(25,6)} = {DAILY_MIN*get_benefit_days(25,6):,}원
  코드 총액 = 42,000 × {get_benefit_days(25,6)} = {42000*get_benefit_days(25,6):,}원 (소정일수 미계산)
""")

# ══════════════════════════════════════════════════════════════════════
sep("7. 경계값 및 소정급여일수 테이블 전체 대조")

print(f"\n[소정급여일수 테이블 — 고용보험법 별표1]")
print(f"{'가입기간':15} {'50세 미만':12} {'50세 이상·장애인':15}")
print("-" * 45)
rows = [
    ("1년 미만(0~11mo)",    120, 120),
    ("1~3년(12~35mo)",      150, 180),
    ("3~5년(36~59mo)",      180, 210),
    ("5~10년(60~119mo)",    210, 240),
    ("10년 이상(120mo+)",   240, 270),
]
for label, u50, o50 in rows:
    print(f"  {label:20} {u50:>6}일       {o50:>6}일")

print(f"""
[경계값 테스트 — code vs law (소정급여일수)]

  가입 179일(~6mo, 25세):
    소정급여일수(법) = {get_benefit_days(25, 5)}일   코드: 미계산 (연령/기간 미사용)
    → UB-3: 입력은 받지만 소정급여일수 계산 없음

  가입 180일(6mo, 25세):
    소정급여일수(법) = {get_benefit_days(25, 6)}일   코드: 미계산
    ※ 수급자격 최소 요건(피보험단위기간 180일)

  가입 12개월(1년 경계, 30세/50세):
    30세: {get_benefit_days(30,11)}일(11mo) → {get_benefit_days(30,12)}일(12mo)   50세: {get_benefit_days(50,11)}일(11mo) → {get_benefit_days(50,12)}일(12mo)

  가입 36개월(3년 경계, 30세/50세):
    30세: {get_benefit_days(30,35)}일(35mo) → {get_benefit_days(30,36)}일(36mo)   50세: {get_benefit_days(50,35)}일(35mo) → {get_benefit_days(50,36)}일(36mo)

  가입 60개월(5년 경계, 30세/50세):
    30세: {get_benefit_days(30,59)}일(59mo) → {get_benefit_days(30,60)}일(60mo)   50세: {get_benefit_days(50,59)}일(59mo) → {get_benefit_days(50,60)}일(60mo)

  가입 120개월(10년 경계, 30세/50세):
    30세: {get_benefit_days(30,119)}일(119mo) → {get_benefit_days(30,120)}일(120mo)
    50세: {get_benefit_days(50,119)}일(119mo) → {get_benefit_days(50,120)}일(120mo)

  연령 49세 vs 50세 (같은 가입기간 24개월):
    49세: {get_benefit_days(49,24)}일   50세: {get_benefit_days(50,24)}일   차이: {get_benefit_days(50,24)-get_benefit_days(49,24)}일
""")

print(f"""
[상한/하한 경계]
  상한 진입점: avg_daily_wage > {round(DAILY_MAX/0.6):,}원 시 code > 법령
  하한 진입점: avg_daily_wage < {round(DAILY_MIN/0.6):,}원 시 code < 법령

  코드 결과 vs 법령:
    avg=80,000원  code={80000*0.6:,.0f}원  법령={law_compute(80000):,}원  {'[NG 과소]' if 80000*0.6 < law_compute(80000) else '[OK]'}
    avg=100,000원 code={100000*0.6:,.0f}원  법령={law_compute(100000):,}원  {'[NG 과소]' if 100000*0.6 < law_compute(100000) else '[OK]'}
    avg={round(DAILY_MIN/0.6):,}원 code={round(DAILY_MIN/0.6)*0.6:,.0f}원  법령={law_compute(round(DAILY_MIN/0.6)):,}원  하한경계
    avg=130,000원 code={130000*0.6:,.0f}원  법령={law_compute(130000):,}원  {'[NG 과대]' if 130000*0.6 > law_compute(130000) else '[OK]'}
    avg=150,000원 code={150000*0.6:,.0f}원  법령={law_compute(150000):,}원  {'[NG 과대]' if 150000*0.6 > law_compute(150000) else '[OK]'}
""")

# ══════════════════════════════════════════════════════════════════════
sep("8. 기준연도 확인")
print(f"""
상한/하한 정의 위치:
  코드 computeResult: 없음 (상한/하한 전혀 미적용)
  legal_basis.draft.yaml: 명시 없음
  config/config.yaml: 미확인 필요
  DB formula: avg_daily_wage*0.6 (비율만, 수치 없음)

하드코딩 없음 → 상한/하한이 코드에 아예 없는 상태 (미구현)
기준연도 문제: 상한/하한이 없으므로 기준연도 부정합 문제도 없으나,
              미구현이 더 큰 문제

참고 수치 (재검증 필요):
  2024~2025년 상한액: 66,000원/일
  2026년 상한액: 66,000원/일 (고용부 미고시 시 동일 추정)
  2026년 하한액: 최저임금(10,030원) × 8h × 80% = {DAILY_MIN:,}원/일 (추정)
""")

# ══════════════════════════════════════════════════════════════════════
sep("9. UI 결과 / forbidden_articles 확인")
html_path = ROOT / "data/workspace/unemployment-benefit/index.html"
html = html_path.read_text(encoding="utf-8")

# forbidden_articles (legal_basis에 없음)
FORBIDDEN = []  # legal_basis forbidden_articles: []
# FAQ 법적 근거 확인
faq_raw = calc.get("faq") or "[]"
faq = json.loads(faq_raw) if isinstance(faq_raw, str) else faq_raw
legal_faq = next((item for item in faq if "법적 근거" in (item.get("question") or item.get("q") or "")), None)

print(f"""
forbidden_articles: [] (legal_basis 기준 — 비어있음, SP-2 유형 없음)
법적 근거 FAQ: {(legal_faq.get('answer') or legal_faq.get('a') or '')[:100] if legal_faq else '없음'}

UI 문제:
  [NG ] result-formula (sub): _formula 미반환 → 계산 과정 미표시 (기존 패턴 UB-6)
  [NG ] total_benefit: SM_CONFIG outputs에 있지만 computeResult 미반환 → detail 0원
  [NG ] out.notices: 없음 (상한/하한/180일 안내 불가)
  [OK ] result-card 노출: daily_benefit 반환됨 (0 이상이면 표시)

HTML 내 "최대 300일" 언급:
""")
lines = html.splitlines()
for i, line in enumerate(lines, 1):
    if "300" in line:
        print(f"  L{i}: {line.strip()[:120]}")

print(f"\nHTML 내 소정급여일수 언급 (240/270 등):")
for i, line in enumerate(lines, 1):
    if re.search(r"\b(120|150|180|210|240|270)\s*일", line):
        print(f"  L{i}: {line.strip()[:120]}")

# ══════════════════════════════════════════════════════════════════════
sep("10. SEO 글 계산 결과 일치 여부")
print("""
본문 L89: "평균 일급이 100,000원이고 고용 기간이 24개월인 경우,
          일일 실업급여는 60,000원이 됩니다. 총 실업급여는 60,000 × 240일 = 14,400,000원"

검증:
  기초일액 = 100,000 × 0.6 = 60,000원
  → 하한({DAILY_MIN:,}원) 적용 시 법령 기초일액 = {DAILY_MIN:,}원 [과소, 법령과 불일치]
  소정급여일수(35세, 24개월) = 150일
  → "240일"이라고 썼으나 법령 소정급여일수는 150일(50세미만·1~3년) [불일치]

  본문 L93: "평균 일급이 80,000원, 실업기간 240일, 총 11,520,000원"
  → 80,000 × 0.6 = 48,000원. 하한({DAILY_MIN:,}원) 적용 시 법령 = {DAILY_MIN:,}원 [불일치]
  → "240일"은 연령/가입기간 미명시, 법령 테이블로 검증 불가
""")

# ══════════════════════════════════════════════════════════════════════
sep("발견 문제 목록 요약")
print(f"""
 ID   심각도   설명                                    패턴 재사용
----------------------------------------------------------------------
 UB-1  major   avg_daily_wage <= 0 null 미반환          YES (SP-3/4)
 UB-2  critical FAQ/본문 "최대 300일" — 법령 최대 270일   NO (콘텐츠 오류)
 UB-3  major   age+employment_months 입력받지만          NO (실업급여 전용)
               소정급여일수 계산에 미사용 (UX 기만)
 UB-4  major   total_benefit computeResult 미반환        NO (출력 누락)
               SM_CONFIG outputs에 있지만 0원 표시
 UB-5  major   상한({DAILY_MAX:,}원)/하한({DAILY_MIN:,}원) 미적용         NO (실업급여 전용)
               → 과대·과소 계산 발생
 UB-6  minor   _formula 미반환 (계산 과정 미표시)        YES (B-4/SP-7)
 UB-7  minor   out.notices 없음                          YES (B-2/SP-1)
 UB-8  minor   하한/상한이 하드코딩 아니라 미구현         NO (유지보수 이슈)
               → 연 1회 갱신 체계 필요
 UB-9  info    법적 근거 FAQ: 고용보험법 조문 번호 미명시  부분 (SP-2 패턴)
               "고용보험법" 법령명만 있고 조항(제46조 등) 없음

공통 패턴 (기존 방식 재사용 가능):
  UB-1  → positive_inputs 주입 (compute_rules 또는 직접 분기)
  UB-6  → _formula 문자열 반환 추가
  UB-7  → out.notices[] 배열 구조

실업급여 전용 (새로운 구현 필요):
  UB-3  → 소정급여일수 2차원 테이블 JS 구현 (age, employment_months)
  UB-4  → total_benefit = daily_benefit × 소정급여일수 (UB-3 선행)
  UB-5  → Math.min(DAILY_MAX, Math.max(DAILY_MIN, base)) 상한/하한 클램프
  UB-2  → DB faq/article_content "300일" → 정확한 소정급여일수로 교체

수정 방향:
  Phase 1 (계산 정확성):
    UB-5: 상한/하한 클램프 추가
    UB-3/UB-4: 소정급여일수 테이블 + total_benefit 계산 추가
    UB-1: positive_inputs 검증 추가
  Phase 2 (콘텐츠 정확성):
    UB-2: "300일" → 소정급여일수 정확 설명으로 교체
    UB-9: FAQ 법적 근거 조항 보강
  Phase 3 (UX):
    UB-6: _formula 반환
    UB-7: out.notices (180일 미만 안내, 상한/하한 안내)
    UB-8: 상한/하한 config 또는 legal_basis에 명시 (연 1회 갱신 체계)
""")
