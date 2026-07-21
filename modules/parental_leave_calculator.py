# -*- coding: utf-8 -*-
"""
modules/parental_leave_calculator.py — 육아휴직급여 계산 엔진 (Phase 2)

계산 흐름 (구현 전 고정, 필수)
1. 입력 검증
2. 수급자격 확인 (피보험단위기간 180일)
3. 특례 적용 여부 판단 — determine_leave_mode()
4. 일반 / 6+6 경로 결정 → calculate_general() / calculate_6plus6()
5. 지급률 적용
6. 월별 상한·하한 적용
7. notices 생성
8. _formula 생성
9. 결과 반환
"""

from datetime import date
from modules.logger import get_logger
from modules.registry_loader import load_registry

LOG = get_logger("parental_leave_calculator")

class ParentalLeaveCalculatorError(Exception):
    pass

# Externalized rates and limits from legal_basis.draft.yaml
def _load_rates_and_limits():
    registry = load_registry()
    return registry.get("육아휴직_급여_계산기", {}).get("benefit_data", {})


def _validate_inputs(monthly_wage: float, insured_period_days: int) -> dict:
    if not isinstance(monthly_wage, (int, float)) or monthly_wage <= 0:
        LOG.warning(f"Invalid monthly_wage: {monthly_wage}")
        return {"error": "통상임금은 0보다 큰 숫자여야 합니다.", "valid": False}
    if not isinstance(insured_period_days, int) or insured_period_days <= 0:
        LOG.warning(f"Invalid insured_period_days: {insured_period_days}")
        return {"error": "피보험단위기간은 0보다 큰 정수여야 합니다.", "valid": False}
    return {"valid": True}


def _check_eligibility(insured_period_days: int) -> bool:
    return insured_period_days >= 180


# --- Calculation Flow Functions ---

def determine_leave_mode(is_dual_earner_parents: bool, child_age_months: int) -> str:
    """
    특례 적용 여부 판단
    - 부모 모두 육아휴직 + 생후 18개월 이내 → SPECIAL_6_PLUS_6
    - 미충족 시 GENERAL
    """
    if is_dual_earner_parents and child_age_months <= 18:
        return "SPECIAL_6_PLUS_6"
    return "GENERAL"


def calculate_general(monthly_wage: float, leave_month: int, rates_and_limits: dict) -> dict:
    """일반 육아휴직 급여 계산"""
    rate = rates_and_limits.get("general_rate", 0.8)
    max_limit = rates_and_limits.get("general_monthly_max", 1500000)
    min_limit = rates_and_limits.get("general_monthly_min", 700000)

    calculated_allowance = monthly_wage * rate
    final_allowance = max(min_limit, min(calculated_allowance, max_limit))

    notices = []
    formula = f"통상임금({monthly_wage}) * {rate*100:.0f}%"

    if calculated_allowance > max_limit:
        notices.append(f"월 상한액 {max_limit:,.0f}원이 적용되었습니다.")
        formula += f" (상한액 {max_limit:,.0f}원 적용)"
    elif calculated_allowance < min_limit:
        notices.append(f"월 하한액 {min_limit:,.0f}원이 적용되었습니다.")
        formula += f" (하한액 {min_limit:,.0f}원 적용)"
    
    return {"allowance": final_allowance, "notices": notices, "_formula": formula, "rate_applied": rate}


def calculate_6plus6(monthly_wage: float, leave_month: int, rates_and_limits: dict) -> dict:
    """
    6+6 특례 육아휴직 급여 계산
    - 1~6개월: 통상임금의 100%, 월별 상한 적용
    - 7개월부터는 일반 경로 전환
    """
    if leave_month > 6:
        LOG.info(f"6+6 특례 {leave_month}개월차: 7개월차부터 일반 육아휴직 경로로 전환됩니다.")
        result = calculate_general(monthly_wage, leave_month, rates_and_limits)
        result["notices"].insert(0, "7개월차부터 6+6 특례가 종료되고 일반 육아휴직 급여 기준이 적용됩니다.")
        result["_formula"] = "(6+6 특례 7개월차부터 일반 경로) " + result["_formula"]
        return result

    special_rates = rates_and_limits.get("special_6_plus_6_rates", {})
    special_rate_data = special_rates.get(str(leave_month))

    if not special_rate_data:
        raise ParentalLeaveCalculatorError(f"6+6 특례 {leave_month}개월차 지급률/상한액 정보를 찾을 수 없습니다.")

    rate = special_rate_data.get("rate", 1.0) # 기본 100%
    max_limit = special_rate_data.get("max_limit", 0)
    
    calculated_allowance = monthly_wage * rate
    final_allowance = min(calculated_allowance, max_limit) if max_limit > 0 else calculated_allowance
    
    notices = []
    formula = f"통상임금({monthly_wage}) * {rate*100:.0f}%"

    if calculated_allowance > max_limit and max_limit > 0:
        notices.append(f"6+6 특례 {leave_month}개월차 월 상한액 {max_limit:,.0f}원이 적용되었습니다.")
        formula += f" (상한액 {max_limit:,.0f}원 적용)"

    return {"allowance": final_allowance, "notices": notices, "_formula": formula, "rate_applied": rate}


def calculate_parental_leave_allowance(
    monthly_wage: float,
    insured_period_days: int,
    is_dual_earner_parents: bool,
    child_age_months: int,
) -> dict:
    """
    육아휴직 급여 계산의 메인 함수.
    입력:
    - monthly_wage: 통상임금
    - insured_period_days: 피보험단위기간 (일)
    - is_dual_earner_parents: 부모 모두 육아휴직 사용 여부 (6+6 특례 판단용)
    - child_age_months: 자녀 생후 개월수 (6+6 특례 판단용)
    출력:
    - monthly_allowance: 월별 육아휴직 급여
    - notices: 안내 메시지 배열
    - _formula: 적용된 계산식 요약
    """
    
    # 1. 입력 검증
    validation = _validate_inputs(monthly_wage, insured_period_days)
    if not validation["valid"]:
        return {"monthly_allowance": None, "notices": [validation["error"]], "_formula": ""}

    # 2. 수급자격 확인
    if not _check_eligibility(insured_period_days):
        return {"monthly_allowance": None, "notices": ["피보험단위기간 180일 이상을 충족해야 합니다."], "_formula": ""}

    rates_and_limits = _load_rates_and_limits()
    if not rates_and_limits:
        raise ParentalLeaveCalculatorError("법적 근거 데이터(지급률/상한액)를 로드할 수 없습니다.")

    monthly_allowances = []
    all_notices = []
    all_formulas = []

    for leave_month in range(1, 19): # 1개월차부터 최대 18개월차까지 계산 (6+6 특례는 6개월 이후 일반으로 전환)
        leave_mode = determine_leave_mode(is_dual_earner_parents, child_age_months)
        
        if leave_mode == "SPECIAL_6_PLUS_6" and leave_month <= 6: # 6+6 특례 1~6개월차
            result = calculate_6plus6(monthly_wage, leave_month, rates_and_limits)
            all_notices.extend([n for n in result["notices"] if n not in all_notices]) # 중복 제거
            all_formulas.append(f"{leave_month}개월차: {result["_formula"]}")
            monthly_allowances.append(result["allowance"])
        elif leave_mode == "SPECIAL_6_PLUS_6" and leave_month > 6: # 6+6 특례 7개월차부터 일반 전환
            result = calculate_6plus6(monthly_wage, leave_month, rates_and_limits) # calculate_6plus6 내부에서 일반으로 전환 처리
            all_notices.extend([n for n in result["notices"] if n not in all_notices]) # 중복 제거
            all_formulas.append(f"{leave_month}개월차: {result["_formula"]}")
            monthly_allowances.append(result["allowance"])
        else: # 일반 육아휴직 (또는 6+6 특례 미충족)
            if is_dual_earner_parents and child_age_months <= 18: # 6+6 특례 조건을 충족하지만 일반 경로로 계산되는 경우
                # 부모 모두 육아휴직 사용 + 생후 18개월 이내' 조건은 충족하나, 특례 기간(6개월)이 지나거나 다른 이유로 일반 경로가 되는 경우
                general_notices = ["부모 모두 육아휴직 사용 및 자녀 생후 18개월 이내 조건은 충족하나, 6+6 특례 기간이 아니므로 일반 육아휴직 급여 기준이 적용됩니다."]
            else:
                general_notices = [f"6+6 특례 조건('부모 모두 육아휴직 사용' 및 '자녀 생후 18개월 이내')을 충족하지 못하여 일반 육아휴직 급여 기준이 적용됩니다."]
            
            result = calculate_general(monthly_wage, leave_month, rates_and_limits)
            current_notices = result["notices"]
            current_notices.extend([n for n in general_notices if n not in current_notices])
            all_notices.extend([n for n in current_notices if n not in all_notices])
            all_formulas.append(f"{leave_month}개월차: {result["_formula"]}")
            monthly_allowances.append(result["allowance"])
    
    final_notices = []
    # 상한액/하한액 적용 안내를 notices 배열 맨 앞으로 이동
    # 상한액/하한액 적용 안내를 notices 배열 맨 앞으로 이동
    # 특례 미충족으로 일반 적용된 경우 안내, 우선순위 명시
    # 공통 면책 문구 추가 (레지스트리에서 가져오기)
    disclaimer = rates_and_limits.get("disclaimer", "")
    if disclaimer and disclaimer not in all_notices:
        final_notices.append(disclaimer)

    # 상한/하한 적용 안내 메시지를 notices 배열 맨 앞으로 이동
    for notice in all_notices:
        if "상한액" in notice or "하한액" in notice:
            final_notices.insert(0, notice)
        elif "특례가 종료되고 일반" in notice:
            final_notices.insert(0, notice)
        elif "특례 조건(\'부모 모두 육아휴직" in notice:
            final_notices.insert(0, notice)
        elif notice not in final_notices: # 중복 방지
            final_notices.append(notice)

    return {
        "monthly_allowance": monthly_allowances,
        "notices": final_notices,
        "_formula": " / ".join(all_formulas),
    }
