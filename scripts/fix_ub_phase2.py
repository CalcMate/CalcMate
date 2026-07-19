# -*- coding: utf-8 -*-
"""Phase 2: unemployment-benefit DB faq + article_content 수정
 - UB-2: '300일' → '120~270일' (고용보험법 별표1 현행)
 - UB-9: FAQ 법령 근거 보강
 - 예시 금액: compute_ub() 함수 실행 결과값만 사용 (수기 계산 금지)
"""
import sys, os, json, copy
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository
from tests.test_unemployment_benefit_compute import compute_ub

cfg = load_config()
db = get_db_adapter(cfg)
calc_repo = CalculatorRepository(db)
calcs = calc_repo.get_all()
ub = next((c for c in calcs if c.get("slug") == "unemployment-benefit"), None)
if not ub:
    print("[ERROR] unemployment-benefit 없음")
    sys.exit(1)

# ── 계산 함수 실행 → 예시값 확정 (수기 계산 금지) ─────────────────────────────
# 케이스 A: 35세, 24개월, 일급 100,000원
A = compute_ub(100_000, 35, 24)  # daily=64192, days=150, total=9,628,800
# 케이스 D: 40세, 36개월, 일급 80,000원
D = compute_ub(80_000, 40, 36)   # daily=64192, days=180, total=11,554,560
# 케이스 C: 55세, 120개월, 일급 130,000원 (상한 클램프)
C = compute_ub(130_000, 55, 120) # daily=66000, days=270, total=17,820,000

assert A["daily_benefit"] == 64192 and A["benefit_days"] == 150
assert D["daily_benefit"] == 64192 and D["benefit_days"] == 180
assert C["daily_benefit"] == 66000 and C["benefit_days"] == 270
print("[예시값 확인] A/D/C 모두 함수 실행 결과 일치")

# ── DB faq 수정 ───────────────────────────────────────────────────────────────
faq_raw = ub.get("faq") or "[]"
faq = json.loads(faq_raw) if isinstance(faq_raw, str) else copy.deepcopy(faq_raw)
orig = copy.deepcopy(faq)

# faq[0]: 누구에게 지급되나요 — "최대 300일" → "120~270일"
faq[0]["answer"] = (
    "실업급여(구직급여)는 고용보험에 가입한 근로자가 비자발적으로 실직한 경우 지급됩니다. "
    "소정급여일수는 피보험단위기간과 연령에 따라 120~270일로 결정되며 "
    "(고용보험법 제45조 및 별표1), 고용센터의 수급자격 심사를 거쳐야 합니다."
)

# faq[2]: 어떻게 계산하나요 — "최대 300일" 제거, 상한/하한 법령 인용
faq[2]["answer"] = (
    "구직급여 = 평균 일급 × 0.6 × 소정급여일수입니다 (고용보험법 제45조·제46조). "
    f"단, 일 구직급여는 상한 {C['daily_benefit']:,}원(고용노동부 고시)과 "
    f"하한 {A['daily_benefit']:,}원(최저임금 × 8 × 0.8, 고용보험법 제46조 제2항)이 적용됩니다. "
    f"예시: 평균 일급 {100_000:,}원, 35세, 가입 24개월 → "
    f"일 구직급여 {A['daily_benefit']:,}원(하한 적용) × {A['benefit_days']}일 = {A['total_benefit']:,.0f}원."
)

# faq[4]: 법적 근거 보강 (UB-9)
faq[4]["answer"] = (
    "실업급여의 법적 근거는 고용보험법입니다. "
    "수급 요건(피보험단위기간 180일 이상, 비자발적 이직 등)은 제40조·제58조에, "
    "급여액 계산(0.6 비율)과 상한·하한은 제45조·제46조에, "
    "소정급여일수(가입기간·연령별 120~270일)는 제45조 및 별표1에 규정되어 있습니다. "
    "최종 수급 여부는 고용센터 심사 결과에 따라 달라질 수 있습니다."
)

# faq[6]: 수급 기간 — "5년 이상 300일" 삭제, 전체 구간 설명
faq[6]["answer"] = (
    "소정급여일수는 피보험단위기간과 연령에 따라 결정됩니다 (고용보험법 별표1). "
    "50세 미만: 1년 미만 120일 / 1~3년 150일 / 3~5년 180일 / 5~10년 210일 / 10년 이상 240일. "
    "50세 이상: 1년 미만 120일 / 1~3년 180일 / 3~5년 210일 / 5~10년 240일 / 10년 이상 270일. "
    "최대 270일이며, 법령에 '300일'은 없습니다."
)

# 변경 확인 출력
for i in [0, 2, 4, 6]:
    changed = faq[i]["answer"] != orig[i]["answer"]
    print(f"  [faq{i}] {'변경' if changed else '동일'}")

calc_repo.update(ub["id"], {"faq": json.dumps(faq, ensure_ascii=False)})
print("[완료] DB faq 업데이트")

# ── article_content 수정 ──────────────────────────────────────────────────────
ac = ub.get("article_content") or ""

NEW_AC = f"""<h1>실업급여 계산기로 쉽고 빠르게 확인하기</h1>
<p>평균 일급과 나이, 고용 기간을 입력해 예상 구직급여를 간편하게 계산해보세요. 고용보험법 제45조·제46조 기준으로 소정급여일수·상한·하한을 자동 적용합니다.</p>

<h2>1. 입력: 계산기 입력폼 안내</h2>
<p>아래 입력 폼에 평균 일급, 나이, 고용 기간(개월)을 입력해주시기 바랍니다. 피보험단위기간이 6개월(약 180일) 미만이면 수급 불가 안내가 표시됩니다.</p>
<form>
    <label for="avg_daily_wage">평균 일급:</label>
    <input type="number" id="avg_daily_wage" name="avg_daily_wage" required>

    <label for="age">나이:</label>
    <input type="number" id="age" name="age" required>

    <label for="employment_months">고용 기간(개월):</label>
    <input type="number" id="employment_months" name="employment_months" required>

    <button type="submit">계산하기</button>
</form>

<h2>2. 결과: 결과 해설</h2>
<p>일 구직급여, 소정급여일수, 총 수령 예상액이 표시됩니다. 예시: 평균 일급 {100_000:,}원, 35세, 가입 24개월인 경우 — 일 구직급여 {A['daily_benefit']:,}원(하한액 적용), 소정급여일수 {A['benefit_days']}일, 총 수령 예상액 {A['total_benefit']:,.0f}원.</p>

<h2>3. 계산 원리</h2>
<p>구직급여는 평균임금의 60%로 계산됩니다. 평균 일급에 0.6을 곱하여 일 구직급여를 구하고, 이 금액에 소정급여일수(가입기간·연령에 따라 120~270일, 고용보험법 별표1)를 곱해 총 급여를 산정합니다.</p>
<p>예시: 평균 일급 {80_000:,}원, 40세, 가입 36개월 → 일급 × 0.6 = {80_000*0.6:,.0f}원이지만 하한({D['daily_benefit']:,}원, 고용보험법 제46조 제2항)이 적용되어 일 구직급여는 {D['daily_benefit']:,}원. 소정급여일수 {D['benefit_days']}일(50세 미만·3~5년) → 총 수령 예상액 {D['total_benefit']:,.0f}원.</p>

<h2>4. 주의사항</h2>
<ul>
    <li>실업급여는 고용보험에 가입한 근로자에게만 지급됩니다. 피보험단위기간이 180일 이상이어야 합니다 (고용보험법 제40조).</li>
    <li>자발적 퇴사 또는 정당한 이유 없이 퇴사한 경우 실업급여를 받을 수 없습니다 (고용보험법 제58조).</li>
    <li>일 구직급여에는 상한(고용노동부 고시)과 하한(최저임금 × 8 × 0.8, 고용보험법 제46조 제2항)이 적용됩니다.</li>
</ul>

<h2>5. 자주 묻는 질문</h2>
<dl>
    <dt>실업급여는 누구에게 지급되나요?</dt>
    <dd>비자발적으로 실직한 고용보험 가입 근로자에게 지급됩니다. 소정급여일수는 가입기간·연령에 따라 120~270일입니다 (고용보험법 제45조 및 별표1).</dd>

    <dt>어떤 경우에 실업급여를 받을 수 없나요?</dt>
    <dd>자발적 퇴사나 정당한 이유 없는 비자발적 퇴사 시 지급되지 않습니다 (고용보험법 제58조).</dd>

    <dt>실업급여는 어떻게 계산하나요?</dt>
    <dd>일 구직급여 = 평균 일급 × 0.6 (상한·하한 클램프 적용). 총 급여 = 일 구직급여 × 소정급여일수 (고용보험법 제45조·제46조).</dd>

    <dt>실업급여 수급 자격에 대한 흔한 오해는 무엇인가요?</dt>
    <dd>실업급여는 신청 후 고용센터의 수급자격 심사를 거쳐 지급됩니다. 최종 수급 여부는 심사 결과에 따라 달라질 수 있습니다.</dd>

    <dt>실업급여 신청 시 유의해야 할 사항은 무엇인가요?</dt>
    <dd>정확한 고용보험 가입 기간과 평균 임금을 기재해야 합니다.</dd>

    <dt>실업급여 수급 기간은 어떻게 되나요?</dt>
    <dd>소정급여일수는 가입기간·연령에 따라 120~270일입니다. 50세 미만 최대 240일, 50세 이상 최대 270일이며, 법령에 '300일'은 없습니다 (고용보험법 별표1).</dd>

    <dt>실업급여를 받기 위해 필요한 서류는 무엇인가요?</dt>
    <dd>실업신고서, 고용보험 가입 증명서, 퇴사한 근로계약서 등이 필요합니다.</dd>
</dl>

<h2>6. 관련 계산기</h2>
<p>비슷한 계산기를 찾고 계신가요? 재직 기간에 따른 퇴직 금액 계산기, 국민연금 계산기 등도 추천합니다.</p>

<h2>7. CTA</h2>
<p>아래 SalaryMate 계산기를 이용하면 자동으로 계산할 수 있습니다. 간편하게 실업급여를 확인해보세요!</p>"""

print()
print("[article_content 예시값 검증]")
print(f"  케이스A: daily={A['daily_benefit']:,} days={A['benefit_days']} total={A['total_benefit']:,.0f}")
print(f"  케이스D: daily={D['daily_benefit']:,} days={D['benefit_days']} total={D['total_benefit']:,.0f}")

calc_repo.update(ub["id"], {"article_content": NEW_AC})
print("[완료] DB article_content 업데이트")
