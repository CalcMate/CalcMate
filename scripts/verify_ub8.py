# -*- coding: utf-8 -*-
"""UB-8: legal_basis.draft.yaml benefit_amounts 외부화 확인"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from modules.registry_loader import load_registry

reg = load_registry(force=True)
ub = reg.get("unemployment-benefit", {})
ba = ub.get("benefit_amounts", {})
bdt = ub.get("benefit_days_table", {})

print("[UB-8] legal_basis.draft.yaml 외부화 확인")
print(f"  daily_max        = {ba.get('daily_max')}")
print(f"  min_wage_hourly  = {ba.get('min_wage_hourly')}")
print(f"  하한 계산값      = {round(ba.get('min_wage_hourly',0) * 8 * 0.8)}")
print(f"  under_50 rows    = {len(bdt.get('under_50', []))}개")
print(f"  age_50_plus rows = {len(bdt.get('age_50_plus', []))}개")

# 하드코딩 없이 yaml에서 로드됐는지 확인
assert ba.get("daily_max") == 66000, "daily_max yaml 불일치"
assert ba.get("min_wage_hourly") == 10030, "min_wage_hourly yaml 불일치"
assert len(bdt.get("under_50", [])) == 5, "under_50 5행 기대"
assert len(bdt.get("age_50_plus", [])) == 5, "age_50_plus 5행 기대"

print()
print("[OK] UB-8: yaml에서 하드코딩 없이 수치 로드 확인")
