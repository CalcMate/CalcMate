# -*- coding: utf-8 -*-
"""four-insurances article_content 완전 재작성 (중복 항목 정리)."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

NP_RATE, NP_MIN, NP_MAX = 0.045, 390_000, 6_170_000
HI_RATE, LTC_RATE, EI_RATE = 0.03545, 0.1296, 0.009

def compute_fi(salary):
    np_base = min(max(salary, NP_MIN), NP_MAX)
    np  = np_base * NP_RATE
    hi  = salary * HI_RATE
    ltc = hi * LTC_RATE
    ei  = salary * EI_RATE
    return {"np": round(np), "hi": round(hi), "ltc": round(ltc),
            "ei": round(ei), "total": round(np + hi + ltc + ei)}

r = compute_fi(3_000_000)
NP, HI, LTC, EI, TOTAL = r["np"], r["hi"], r["ltc"], r["ei"], r["total"]

# 이중 검증
assert NP + HI + LTC + EI == TOTAL
assert TOTAL == 282_133

cfg  = load_config()
db   = get_db_adapter(cfg)
repo = CalculatorRepository(db)
calcs = repo.get_all()
fi = next((c for c in calcs if c.get("slug") == "four-insurances"), None)
calc_id = fi["id"]

new_article = f"""<h1>4대보험 계산기 - 월급여로 쉽게 계산</h1>
<p>저희 4대보험 계산기를 통해 월급여를 입력하면 국민연금, 건강보험, 장기요양보험, 고용보험을 자동으로 계산해 드립니다. 정확한 보험료를 손쉽게 확인하세요!</p>

<h2>입력</h2>
<p>아래 입력폼에 월급여를 입력해 주세요.</p>
<form>
    <label for="monthly_salary">월급여 (원): </label>
    <input type="number" id="monthly_salary" name="monthly_salary" required>
    <button type="submit">계산하기</button>
</form>

<h2>결과</h2>
<p>결과는 아래와 같이 표시됩니다:</p>
<ul>
    <li>국민연금: <span id="national_pension">0</span> 원</li>
    <li>건강보험: <span id="health_insurance">0</span> 원</li>
    <li>장기요양보험: <span id="long_term_care">0</span> 원</li>
    <li>고용보험: <span id="employment_insurance">0</span> 원</li>
    <li>총 합계: <span id="total">0</span> 원</li>
</ul>

<h2>계산 원리</h2>
<p>4대보험 각 항목은 월급여를 바탕으로 비율을 적용하여 계산됩니다.</p>
<ul>
    <li>국민연금은 월급여의 4.5%로 계산됩니다. 단, 기준소득월액 하한(39만 원)~상한(617만 원) 범위가 적용됩니다. 월급여 300만 원이라면 300만 원 × 4.5% = {NP//10000}만 {(NP%10000)//1000}천 원입니다.</li>
    <li>건강보험은 월급여의 3.545%입니다. 같은 사례에서 300만 원 × 3.545% = {HI//10000}만 {(HI%10000)//1000}천 {HI%1000}원이 됩니다.</li>
    <li>장기요양보험은 건강보험료의 12.96%입니다. 건강보험료({HI//10000}만 {(HI%10000)//1000}천 {HI%1000}원) × 12.96% = {LTC//10000}만 {(LTC%10000)//1000}천 {LTC%1000}원이 됩니다.</li>
    <li>고용보험은 월급여의 0.9%로, 300만 원 × 0.9% = {EI//10000}만 {(EI%10000)//1000}천 원입니다.</li>
    <li>이 모든 금액을 합하면, 총 보험료는 {NP//10000}만 {(NP%10000)//1000}천 원 + {HI//10000}만 {(HI%10000)//1000}천 {HI%1000}원 + {LTC//10000}만 {(LTC%10000)//1000}천 {LTC%1000}원 + {EI//10000}만 {(EI%10000)//1000}천 원 = {TOTAL//10000}만 {(TOTAL%10000)//1000}천 {TOTAL%1000}원이 됩니다. (산재보험은 사업주 전액 부담으로 미포함)</li>
</ul>

<h2>주의사항</h2>
<ul>
    <li>월급여에 따라 보험료가 달라지므로 정확한 금액을 입력해 주세요.</li>
    <li>4대보험의 적용 여부는 근로계약의 조건에 따라 다를 수 있습니다.</li>
    <li>고용보험은 근로자 0.9%, 사업주 0.9%+α(규모별 추가)로 부담 비율이 다릅니다.</li>
    <li><strong>산재보험은 사업주가 전액 부담합니다</strong> — 근로자 급여에서 공제되지 않으며 이 계산기에 표시되지 않습니다 (산업재해보상보험법 제13조).</li>
</ul>

<h2>자주 묻는 질문</h2>
<dl>
    <dt>4대 보험 지급 조건은 어떻게 되나요?</dt>
    <dd>4대 보험은 월 급여를 받는 근로자가 가입할 수 있으며, 노동 계약에 따라 정규직 또는 비정규직 여부와 관계없이 매월 급여를 지급받는 경우 적용됩니다.</dd>

    <dt>4대 보험을 받지 못하는 예외 사항은 무엇인가요?</dt>
    <dd>단기 계약 근로자, 일용직 근로자, 소규모 사업장의 근로자 등 특정 조건을 만족하지 않을 경우 적용 제외가 될 수 있습니다.</dd>

    <dt>4대 보험은 어떻게 계산하나요?</dt>
    <dd>국민연금 4.5%(기준소득월액 상한·하한 적용), 건강보험 3.545%, 장기요양보험(건강보험료 × 12.96%), 고용보험 0.9%를 계산하여 합산합니다. 월급여 300만 원 기준 합계 {TOTAL//10000}만 {(TOTAL%10000)//1000}천 {TOTAL%1000}원.</dd>

    <dt>4대 보험 계산 시 자주 틀리는 부분은 무엇인가요?</dt>
    <dd>근로자와 사용자 부담 금액을 혼동해 잘못 계산하는 경우가 많습니다.</dd>

    <dt>4대 보험의 법적 근거는 무엇인가요?</dt>
    <dd>4대 보험은 관련 법령에 따라 강제적으로 운영됩니다.</dd>

    <dt>4대 보험 사용 시 실무 팁은 무엇인가요?</dt>
    <dd>매월 급여를 정확히 입력하고, 변경 시 신속하게 보험 가입 상태를 업데이트하는 것이 중요합니다.</dd>
</dl>

<h2>관련 계산기</h2>
<ul>
    <li><a href="#">퇴직금 계산기</a></li>
    <li><a href="#">연봉 계산기</a></li>
</ul>

<h2>CTA</h2>
<p>아래 SalaryMate 계산기를 이용하면 자동으로 계산할 수 있습니다. 쉽게 4대보험을 계산해 보고, 월급에 맞는 정확한 보험료를 확인하세요!</p>"""

repo.update(calc_id, {"article_content": new_article})
print("[DB] article_content 완전 재작성 완료")

# 최종 검증
calcs2 = repo.get_all()
fi2 = next((c for c in calcs2 if c.get("slug") == "four-insurances"), None)
art2 = fi2.get("article_content") or ""

forbidden = ["106,500", "10만 6천 500", "268,500", "26만 8천 500",
             "각 보험료는 근로자와 사용자가 절반씩 부담"]
ok = True
for v in forbidden:
    if v in art2:
        print(f"[NG] 잔존: {v!r}")
        ok = False
    else:
        print(f"[OK] 없음: {v!r}")

# 중복 확인
ltc_count = art2.count("장기요양보험:")
if ltc_count > 1:
    print(f"[NG] 장기요양보험 결과 행 중복: {ltc_count}건")
    ok = False
else:
    print(f"[OK] 장기요양보험 결과 행 중복 없음")

# 장기요양보험 계산원리 중복 확인
ltc_calc_count = art2.count("장기요양보험은 건강보험료의")
if ltc_calc_count > 1:
    print(f"[NG] 장기요양보험 계산 설명 중복: {ltc_calc_count}건")
    ok = False
else:
    print(f"[OK] 장기요양보험 계산 설명 중복 없음")

if ok:
    print("\n>>> article_content 검증 PASS")
else:
    print("\n>>> 검증 실패")
    sys.exit(1)
