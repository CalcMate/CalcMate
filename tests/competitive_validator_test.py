# -*- coding: utf-8 -*-
"""tests/competitive_validator_test.py — CompetitiveValidator 테스트"""
import pytest
from modules.competitive_analysis.competitive_validator import CompetitiveValidator

@pytest.fixture
def validator():
    return CompetitiveValidator()

def test_validate_pass(validator):
    """Test 1: 정상 Gap + Task"""
    gap = {"missing_topics": ["FAQ"], "priority": "HIGH"}
    tasks = {"tasks": [{"topic": "FAQ", "priority": "HIGH", "action": "추가", "reason": "보완"}]}
    
    result = validator.validate(gap, tasks)
    assert result["status"] == "PASS"

def test_validate_legal_hold(validator):
    """Test 2: 법적 근거 없는 개선 Task -> HOLD"""
    gap = {"missing_topics": ["법적 기준"], "priority": "HIGH"}
    tasks = {"tasks": [{"topic": "법적 기준", "priority": "HIGH", "action": "임의 법령 추가", "reason": "필요"}]}
    
    result = validator.validate(gap, tasks)
    assert result["status"] == "HOLD"

def test_validate_duplicate_warning(validator):
    """Test 3: 복사 위험 Task -> WARNING"""
    gap = {"missing_topics": ["예시"], "priority": "MEDIUM"}
    tasks = {"tasks": [{"topic": "예시", "priority": "MEDIUM", "action": "경쟁사 내용 복사", "reason": "필요"}]}
    
    result = validator.validate(gap, tasks)
    assert result["status"] == "WARNING"
