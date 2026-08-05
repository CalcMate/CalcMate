# -*- coding: utf-8 -*-
"""tests/faq_source_mapper_test.py — FAQ 시스템 테스트"""
import pytest
from modules.faq_engine.faq_source_mapper import mapper
from modules.faq_engine.faq_validator import FAQValidator

def test_mapper_data_exists():
    assert mapper.get_source_data("weekly-holiday-allowance", "legal_question") is not None

def test_validator_pass_scenario():
    validator = FAQValidator()
    # 주휴수당에 대한 정상 답변
    content = "주휴수당의 법적 근거는 근로기준법 제55조입니다."
    is_valid, msg = validator.validate(content, "legal_question", "weekly-holiday-allowance")
    assert is_valid is True
    assert msg == "검증 통과"

def test_validator_hold_scenario():
    validator = FAQValidator()
    # 잘못된 답변 (근거 누락)
    content = "주휴수당은 그냥 받을 수 있습니다."
    is_valid, msg = validator.validate(content, "legal_question", "weekly-holiday-allowance")
    assert is_valid is False
    assert "HOLD" in msg

def test_validator_condition_violation_hold():
    validator = FAQValidator()
    # 잘못된 답변 (10시간 근무 시 가능하다고 명시 -> 계산 규칙 위반)
    content = "10시간 근무해도 주휴수당을 받을 수 있습니다."
    is_valid, msg = validator.validate(content, "calculation_logic", "weekly-holiday-allowance")
    assert is_valid is False
    assert "HOLD: 계산 규칙 위반" in msg
