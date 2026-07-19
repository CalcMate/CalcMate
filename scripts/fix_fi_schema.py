# -*- coding: utf-8 -*-
"""four-insurances: output_schema에 long_term_care 추가 + formula 갱신"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

cfg = load_config()
db  = get_db_adapter(cfg)
repo = CalculatorRepository(db)

calcs = repo.get_all()
fi = next((c for c in calcs if c.get("slug") == "four-insurances"), None)
assert fi, "four-insurances 계산기를 찾을 수 없음"

calc_id = fi["id"]

# ── output_schema 업데이트 ──────────────────────────────────────────────────
old_out = json.loads(fi.get("output_schema") or "{}")
print(f"[이전] output_schema: {json.dumps(old_out, ensure_ascii=False)}")

new_out = {
    "national_pension":    "number",
    "health_insurance":    "number",
    "long_term_care":      "number",
    "employment_insurance":"number",
    "total":               "number",
}
repo.update(calc_id, {"output_schema": json.dumps(new_out, ensure_ascii=False)})
print(f"[이후] output_schema: {json.dumps(new_out, ensure_ascii=False)}")

# ── formula 갱신 (참고용 메타데이터, 실제 계산은 _compute_js 전용 분기가 담당) ──
new_formula = {
    "national_pension":    "clamp(monthly_salary,390000,6170000)*0.045",
    "health_insurance":    "monthly_salary*0.03545",
    "long_term_care":      "health_insurance*0.1296",
    "employment_insurance":"monthly_salary*0.009",
    "total":               "national_pension+health_insurance+long_term_care+employment_insurance",
}
repo.update(calc_id, {"formula": json.dumps(new_formula, ensure_ascii=False)})
print(f"[이후] formula: {json.dumps(new_formula, ensure_ascii=False, indent=2)}")

print("\nDone — output_schema + formula 업데이트 완료")
