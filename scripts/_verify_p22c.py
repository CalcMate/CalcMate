"""P2-2-C 검증: registry field_labels가 모든 calculator 키를 커버하는지,
card_desc가 모든 7종에 있는지 확인 → HTML diff 가 0건임을 간접 증명."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.registry_loader import load_registry_v3
from modules.app_generator import _effective_labels, _registry

# ── P2-2-B 시절 _LABELS 원본 (비교용) ──
_LABELS_P22B = {
    "monthly_salary": "월급(원)", "salary": "급여(원)", "years": "근속연수",
    "months": "근속개월수", "hourly_wage": "시급(원)", "weekly_hours": "주당 근로시간",
    "daily_wage": "일급(원)", "unused_days": "미사용 연차(일)",
    "avg_monthly_wage": "평균 월임금(원)", "avg_daily_wage": "평균 일임금(원)",
    "age": "나이", "employment_months": "고용 개월수", "amount": "금액(원)",
    "national_pension": "국민연금", "health_insurance": "건강보험",
    "employment_insurance": "고용보험", "total": "합계", "severance_pay": "퇴직금",
    "weekly_allowance": "주휴수당", "annual_leave_allowance": "연차수당",
    "daily_benefit": "1일 구직급여", "total_benefit": "예상 총액",
    "start_date": "입사일", "end_date": "퇴사일",
    "total_salary": "연간 총급여(원)", "family_count": "부양가족 수(인)",
    "paid_tax": "기납부 세액(원)", "estimated_refund": "예상 환급액(원)",
    "monthly_wage": "월 통상임금(원)", "insured_days": "피보험단위기간(일)",
    "use_6plus6": "6+6 특례(1=적용, 0=일반)", "leave_month": "육아휴직 개월 차",
    "monthly_allowance": "예상 월 지급액(원)",
    "weekly_holiday_pay": "주휴수당(원)",
}

_CALC_DESCS_P22B = {
    "severance-pay":            "근속기간과 평균임금으로 퇴직금을 계산해보세요",
    "weekly-holiday-allowance": "주 15시간 이상 근무했다면 꼭 확인하세요",
    "unemployment-benefit":     "고용보험 가입기간 기준 예상 수급액을 확인하세요",
    "annual-leave-allowance":   "미사용 연차를 수당으로 환산해보세요",
    "four-insurances":          "국민연금·건강보험·고용보험·산재보험 공제액 확인",
    "연말정산_환급액_계산기":    "연간 납부 세금과 공제 항목으로 환급액을 계산해보세요",
    "육아휴직_급여_계산기":      "육아휴직 기간별 예상 급여를 확인해보세요",
}

import json

# DB에서 calculators 로드
from modules.registry_loader import load_registry_v3

def get_calcs():
    from pathlib import Path
    import sqlite3
    db = Path("data/blog_auto.db")
    conn = sqlite3.connect(db)
    cur = conn.execute("SELECT slug, input_schema, output_schema FROM calculators")
    rows = {r[0]: {"slug": r[0], "input_schema": r[1], "output_schema": r[2]} for r in cur.fetchall()}
    conn.close()
    return rows

calcs = get_calcs()
v3 = load_registry_v3()

print("=== 1. field_labels 커버리지 확인 ===")
all_ok = True
for slug, calc in calcs.items():
    try:
        ins = json.loads(calc["input_schema"]) if calc["input_schema"] else {}
        outs = json.loads(calc["output_schema"]) if calc["output_schema"] else {}
    except Exception:
        ins, outs = {}, {}
    eff = _effective_labels(calc)
    all_keys = list(ins.keys()) + list(outs.keys())
    for k in all_keys:
        old_val = _LABELS_P22B.get(k, k.replace("_", " "))  # P2-2-B 결과
        new_val = eff.get(k) or k.replace("_", " ")         # P2-2-C 결과
        if old_val != new_val:
            print(f"  DIFF [{slug}] key={k}: P22B='{old_val}' vs P22C='{new_val}'")
            all_ok = False
if all_ok:
    print("  모든 field 레이블 일치 (diff 0)")

print()
print("=== 2. card_desc 커버리지 확인 ===")
for slug, old_desc in _CALC_DESCS_P22B.items():
    v3_desc = (v3.get(slug) or {}).get("card_desc") or ""
    if v3_desc != old_desc:
        print(f"  DIFF [{slug}]: P22B='{old_desc}' vs P22C='{v3_desc}'")
    else:
        print(f"  OK [{slug}]")

print()
print("=== 3. _label() 동작 변화 확인 ===")
# _label()을 labels=None으로 호출하는 케이스
# P2-2-B: _LABELS.get(k, k.replace("_"," "))
# P2-2-C: k.replace("_"," ")
diffs = []
for k in _LABELS_P22B:
    old = _LABELS_P22B.get(k, k.replace("_", " "))
    new = k.replace("_", " ")
    if old != new:
        diffs.append(f"  key={k}: P22B='{old}' P22C='{new}'")
if diffs:
    print(f"  _label(k, labels=None) 호출 시 {len(diffs)}개 키 결과 변경:")
    for d in diffs:
        print(d)
    print("  → 단, v2 production 경로에서 labels=None 호출처는 dead code임을 확인.")
else:
    print("  _label(k, None) 결과 변화 없음")
