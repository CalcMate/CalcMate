"""
Registry field_labels vs 실제 DB schema 전수 감사.
- 실제 input/output key 중 registry 누락
- registry에는 있으나 schema에 없는 key
- 동일 key의 label 불일치
"""
import sys, os, json, sqlite3
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

from modules.registry_loader import load_registry_v3

# ── P2-2-B 기준 _LABELS (비교 기준) ──
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

DB_PATH = "data/blog_auto.db"
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
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "SELECT slug, input_schema, output_schema FROM calculators WHERE slug IN (%s)"
        % ",".join("?" * len(SLUGS)),
        SLUGS,
    )
    result = {}
    for slug, ins_raw, outs_raw in cur.fetchall():
        try:
            ins = json.loads(ins_raw) if ins_raw else {}
        except Exception:
            ins = {}
        try:
            outs = json.loads(outs_raw) if outs_raw else {}
        except Exception:
            outs = {}
        result[slug] = {"input": ins, "output": outs}
    conn.close()
    return result

v3 = load_registry_v3()
db = load_db_schemas()

print("=" * 70)
print("Registry field_labels vs 실제 DB schema 전수 감사")
print("=" * 70)

missing_input  = {}   # slug → [keys in DB input  but not in registry]
missing_output = {}   # slug → [keys in DB output but not in registry]
extra_registry = {}   # slug → [keys in registry but not in DB schema]
mismatch       = {}   # slug → [(key, registry_label, _LABELS_label)]

for slug in SLUGS:
    reg_entry = v3.get(slug) or {}
    reg_fl    = reg_entry.get("field_labels") or {}
    schema    = db.get(slug, {"input": {}, "output": {}})
    in_keys   = set(schema["input"].keys())
    out_keys  = set(schema["output"].keys())
    all_schema_keys = in_keys | out_keys
    reg_keys  = set(reg_fl.keys())

    # 1. 실제 input key 중 registry 누락
    mi = sorted(in_keys - reg_keys)
    if mi:
        missing_input[slug] = mi

    # 2. 실제 output key 중 registry 누락
    mo = sorted(out_keys - reg_keys)
    if mo:
        missing_output[slug] = mo

    # 3. registry에는 있으나 schema에 없는 key
    ex = sorted(reg_keys - all_schema_keys)
    if ex:
        extra_registry[slug] = ex

    # 4. 동일 key label 불일치 (registry vs _LABELS)
    mm = []
    for k in sorted(reg_keys & set(_LABELS.keys())):
        rv = reg_fl[k]
        lv = _LABELS[k]
        if rv != lv:
            mm.append((k, rv, lv))
    if mm:
        mismatch[slug] = mm

# ── 출력 ──
print()
print("▶ 1. 실제 INPUT key 중 Registry 누락")
if not missing_input:
    print("   NONE")
else:
    for slug, keys in missing_input.items():
        print(f"   [{slug}]: {keys}")

print()
print("▶ 2. 실제 OUTPUT key 중 Registry 누락")
if not missing_output:
    print("   NONE")
else:
    for slug, keys in missing_output.items():
        print(f"   [{slug}]: {keys}")

print()
print("▶ 3. Registry에 있으나 실제 schema에 없는 key (spurious)")
if not extra_registry:
    print("   NONE")
else:
    for slug, keys in extra_registry.items():
        print(f"   [{slug}]: {keys}")

print()
print("▶ 4. 동일 key registry↔_LABELS label 불일치")
if not mismatch:
    print("   NONE")
else:
    for slug, mm in mismatch.items():
        for k, rv, lv in mm:
            print(f"   [{slug}] key={k}: registry='{rv}' / _LABELS='{lv}'")

# ── 계산기별 전체 매핑 테이블 ──
print()
print("=" * 70)
print("▶ 계산기별 전체 key 매핑 현황")
print("=" * 70)
for slug in SLUGS:
    reg_entry = v3.get(slug) or {}
    reg_fl    = reg_entry.get("field_labels") or {}
    schema    = db.get(slug, {"input": {}, "output": {}})
    in_keys   = set(schema["input"].keys())
    out_keys  = set(schema["output"].keys())
    print(f"\n[{slug}]")
    print(f"  INPUT keys  : {sorted(in_keys)}")
    print(f"  OUTPUT keys : {sorted(out_keys)}")
    print(f"  Registry fl : {dict(sorted(reg_fl.items()))}")
