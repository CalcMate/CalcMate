"""
P2-2 Shadow 전수 비교 (확장판)
기존: registry에 있는 key만 비교
확장: 실제 DB schema의 모든 key를 기준으로 registry 커버리지 검증

검증 항목:
  A. 실제 schema key 중 registry field_labels 누락
  B. registry field_labels 중 실제 schema에 없는 허위 key
  C. 동일 key label: registry vs _LABELS (P2-2-B 기준)
  D. display_order vs _SLUG_ORDER 순서 일치
  E. card_desc vs _CALC_DESCS 일치
"""
import sys, os, json, sqlite3
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

from modules.registry_loader import load_registry_v3, invalidate

# P2-2-B 기준 레거시 상수 (비교용 — production 코드에서는 이미 제거됨)
_LABELS = {
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
_SLUG_ORDER = [
    "weekly-holiday-allowance", "severance-pay", "annual-leave-allowance",
    "unemployment-benefit", "four-insurances", "연말정산_환급액_계산기", "육아휴직_급여_계산기",
]

# _SLUG_ORDER -> invalidate cache first so fresh data is used
invalidate()
v3 = load_registry_v3(force=True)

_CALC_DESCS = {
    "severance-pay":            "근속기간과 평균임금으로 퇴직금을 계산해보세요",
    "weekly-holiday-allowance": "주 15시간 이상 근무했다면 꼭 확인하세요",
    "unemployment-benefit":     "고용보험 가입기간 기준 예상 수급액을 확인하세요",
    "annual-leave-allowance":   "미사용 연차를 수당으로 환산해보세요",
    "four-insurances":          "국민연금·건강보험·고용보험·산재보험 공제액 확인",
    "연말정산_환급액_계산기":    "연간 납부 세금과 공제 항목으로 환급액을 계산해보세요",
    "육아휴직_급여_계산기":      "육아휴직 기간별 예상 급여를 확인해보세요",
}

SLUGS = [
    "weekly-holiday-allowance",
    "severance-pay",
    "annual-leave-allowance",
    "unemployment-benefit",
    "four-insurances",
    "연말정산_환급액_계산기",
    "육아휴직_급여_계산기",
]

def load_db_schemas():
    conn = sqlite3.connect("data/blog_auto.db")
    cur = conn.execute(
        "SELECT slug, input_schema, output_schema FROM calculators WHERE slug IN (%s)"
        % ",".join("?" * len(SLUGS)),
        SLUGS,
    )
    result = {}
    for slug, ins_raw, outs_raw in cur.fetchall():
        ins  = json.loads(ins_raw)  if ins_raw  else {}
        outs = json.loads(outs_raw) if outs_raw else {}
        result[slug] = {"input": ins, "output": outs}
    conn.close()
    return result

db = load_db_schemas()

total_issues = 0

print("=" * 70)
print("Shadow 전수 비교 (schema 기준 확장판)")
print("=" * 70)

# ── A. schema key 중 registry 누락 ──────────────────────────────────
print("\n[A] 실제 schema key 중 registry field_labels 누락")
a_issues = 0
for slug in SLUGS:
    reg_fl  = (v3.get(slug) or {}).get("field_labels") or {}
    schema  = db.get(slug, {"input": {}, "output": {}})
    all_keys = set(schema["input"]) | set(schema["output"])
    missing  = sorted(all_keys - set(reg_fl))
    if missing:
        print(f"  MISS [{slug}]: {missing}")
        a_issues += len(missing)
if a_issues == 0:
    print("  PASS - 누락 없음")
total_issues += a_issues

# ── B. registry 허위 key (schema에 없음) ────────────────────────────
print("\n[B] registry field_labels 중 실제 schema에 없는 허위 key")
b_issues = 0
for slug in SLUGS:
    reg_fl  = (v3.get(slug) or {}).get("field_labels") or {}
    schema  = db.get(slug, {"input": {}, "output": {}})
    all_keys = set(schema["input"]) | set(schema["output"])
    spurious = sorted(set(reg_fl) - all_keys)
    if spurious:
        print(f"  SPUR [{slug}]: {spurious}")
        b_issues += len(spurious)
if b_issues == 0:
    print("  PASS - 허위 key 없음")
total_issues += b_issues

# ── C. label 불일치: registry vs _LABELS ────────────────────────────
print("\n[C] 동일 key label registry vs _LABELS 불일치")
c_issues = 0
for slug in SLUGS:
    reg_fl = (v3.get(slug) or {}).get("field_labels") or {}
    schema = db.get(slug, {"input": {}, "output": {}})
    all_keys = set(schema["input"]) | set(schema["output"])
    for k in sorted(all_keys & set(reg_fl) & set(_LABELS)):
        rv = reg_fl[k]
        lv = _LABELS[k]
        if rv != lv:
            print(f"  DIFF [{slug}] key={k}: registry='{rv}' _LABELS='{lv}'")
            c_issues += 1
if c_issues == 0:
    print("  PASS - 불일치 없음")
total_issues += c_issues

# ── D. display_order vs _SLUG_ORDER 순서 ────────────────────────────
print("\n[D] display_order vs _SLUG_ORDER 순서 일치")
d_issues = 0
v3_ordered = sorted(
    [(s, (v3.get(s) or {}).get("display_order", 999)) for s in SLUGS],
    key=lambda x: x[1]
)
v3_order = [s for s, _ in v3_ordered]
if v3_order == list(_SLUG_ORDER):
    print("  PASS - 순서 일치")
    for i, (s, o) in enumerate(v3_ordered, 1):
        so = _SLUG_ORDER[i-1]
        print(f"    {i}. {s} (display_order={o}) == _SLUG_ORDER[{i-1}]={so}")
else:
    print(f"  DIFF: registry={v3_order}")
    print(f"        _SLUG_ORDER={list(_SLUG_ORDER)}")
    d_issues += 1
total_issues += d_issues

# ── E. card_desc vs _CALC_DESCS ─────────────────────────────────────
print("\n[E] card_desc vs _CALC_DESCS 불일치")
e_issues = 0
for slug in SLUGS:
    v3_desc  = (v3.get(slug) or {}).get("card_desc") or ""
    old_desc = _CALC_DESCS.get(slug, "")
    if v3_desc != old_desc:
        print(f"  DIFF [{slug}]: registry='{v3_desc}' / _CALC_DESCS='{old_desc}'")
        e_issues += 1
if e_issues == 0:
    print("  PASS - 전체 일치")
total_issues += e_issues

print()
print("=" * 70)
if total_issues == 0:
    print("RESULT: ALL PASS - 총 이슈 0건")
else:
    print(f"RESULT: FAIL - 총 이슈 {total_issues}건")
print("=" * 70)
