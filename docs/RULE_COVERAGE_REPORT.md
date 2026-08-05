# RULE_COVERAGE_REPORT.md

## unemployment-benefit
- threshold_rule: ✗ (커버리지 없음 - 피보험단위기간 180일은 수급요건, 계산기준 아님)
- numeric_rule: ✗ (커버리지 없음)
- condition_rule: ✓
- exception_rule: ✗ (커버리지 없음)

## 육아휴직_급여_계산기
- threshold_rule: ✓ (min_insured_days)
- numeric_rule: ✓ (general/special ceilings)
- condition_rule: ✓ (special 6+6 rule)
- exception_rule: ✓ (special 6+6 condition)

## four-insurances
- threshold_rule: ✓ (np_min/np_max)
- numeric_rule: ✓ (rates)
- condition_rule: ✓ (eligibility)
- exception_rule: ✗ (커버리지 없음)

## weekly-holiday-allowance
- threshold_rule: ✓ (min_weekly_hours)
- numeric_rule: ✓ (min_wage)
- condition_rule: ✓ (eligibility)
- exception_rule: ✓ (notices)

## severance-pay
- threshold_rule: ✗ (커버리지 없음)
- numeric_rule: ✓ (formula)
- condition_rule: ✓ (eligibility)
- exception_rule: ✗ (커버리지 없음)

## annual-leave-allowance
- threshold_rule: ✗ (커버리지 없음)
- numeric_rule: ✓ (formula)
- condition_rule: ✓ (eligibility)
- exception_rule: ✓ (촉진제도)

## 연말정산_환급액_계산기
- threshold_rule: ✗ (커버리지 없음)
- numeric_rule: ✓ (brackets/deductions)
- condition_rule: ✓ (eligibility)
- exception_rule: ✗ (커버리지 없음)
