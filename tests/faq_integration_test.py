# -*- coding: utf-8 -*-
"""tests/faq_integration_test.py — FAQ Engine 통합 테스트"""
import pytest
from modules.faq_engine.faq_validator import FAQValidator
from modules.faq_engine.faq_source_mapper import mapper

class MockMapper:
    def __init__(self, original_mapper):
        self.original = original_mapper
        self.mocked_rules = {}

    def get_source_data(self, slug, category):
        data = self.original.get_source_data(slug, category)
        if slug in self.mocked_rules:
            if not data: data = {}
            data["compute_rules"] = self.mocked_rules[slug]
        return data

def test_integration_scenarios():
    validator = FAQValidator()
    # Replace mapper in validator for testing
    mock_mapper = MockMapper(mapper)
    validator.mapper = mock_mapper
    
    # 1. Weekly Holiday Allowance Test (Regression)
    mock_mapper.mocked_rules["weekly-holiday-allowance"] = {"min_weekly_hours": 15}
    content = "10시간 근무해도 가능합니다."
    is_valid, msg = validator.validate(content, "calculation_logic", "weekly-holiday-allowance")
    assert is_valid is False
    assert "HOLD" in msg

    # 2. Parental Leave Transition Test
    mock_mapper.mocked_rules["parental-leave-benefit"] = {
        "transition_points": [6, 7],
        "comparison_keywords": ["동일", "같음"]
    }
    # Fail case
    content = "6개월과 7개월 이후는 동일하게 계산됩니다."
    is_valid, msg = validator.validate(content, "calculation_logic", "parental-leave-benefit")
    assert is_valid is False
    assert "HOLD" in msg

    # Pass case
    content = "6개월과 7개월 이후의 급여 계산 조건은 다릅니다."
    is_valid, msg = validator.validate(content, "calculation_logic", "parental-leave-benefit")
    assert is_valid is True
    assert "검증 통과" in msg
