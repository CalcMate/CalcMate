# -*- coding: utf-8 -*-
"""tests/parental_leave_faq_test.py — 육아휴직 FAQ 검증 테스트"""
import pytest
from modules.faq_engine.faq_validator import FAQValidator

@pytest.fixture
def validator():
    return FAQValidator()

def test_parental_leave_case1_period_distortion(validator):
    """Case 1 — 기간 조건 왜곡 (validate_condition_rule)"""
    content = "모든 근로자는 동일하게 최대 18개월 육아휴직을 사용할 수 있습니다."
    # 육아휴직 slug로 테스트 (실제 slug 확인 필요, 여기선 임시 사용)
    is_valid, msg = validator.validate(content, "exception_case", "parental-leave-benefit")
    # 현재는 구현 전이라 False가 아닐 수 있음, 테스트 통과를 위해 임시로 False 예상
    assert is_valid is False
    assert "HOLD" in msg

def test_parental_leave_case2_nonexistent_restriction(validator):
    """Case 2 — 존재하지 않는 제한 생성 (validate_exception_rule)"""
    content = "회사가 승인하지 않으면 육아휴직을 사용할 수 없습니다."
    is_valid, msg = validator.validate(content, "exception_case", "parental-leave-benefit")
    assert is_valid is False
    assert "HOLD" in msg

def test_parental_leave_case3_numeric_mismatch(validator):
    """Case 3 — 숫자 변경 (validate_numeric_rule)"""
    content = "육아휴직 기간은 24개월입니다." # 임의 숫자
    is_valid, msg = validator.validate(content, "calculation_logic", "parental-leave-benefit")
    assert is_valid is False
    assert "HOLD" in msg

def test_parental_leave_case4_transition_distortion(validator):
    """Case 4 — 전환 구간 왜곡 (validate_condition_rule)"""
    content = "6개월까지든 7개월 이후든 육아휴직 급여는 동일하게 계산됩니다."
    is_valid, msg = validator.validate(content, "calculation_logic", "parental-leave-benefit")
    assert is_valid is False
    assert "HOLD" in msg
