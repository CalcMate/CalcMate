# -*- coding: utf-8 -*-
"""tests/competitive_improvement_test.py — ImprovementGenerator 테스트"""
import pytest
from modules.competitive_analysis.improvement_generator import ImprovementGenerator

@pytest.fixture
def generator():
    return ImprovementGenerator()

def test_generate_high_priority(generator):
    """Test 1: HIGH Gap 입력 -> HIGH task 생성"""
    gap_result = {"missing_topics": ["FAQ"], "priority": "HIGH"}
    result = generator.generate(gap_result)
    
    assert len(result["tasks"]) == 1
    assert result["tasks"][0]["priority"] == "HIGH"
    assert result["tasks"][0]["action"] == "FAQ 섹션 추가"

def test_generate_medium_priority(generator):
    """Test 2: MEDIUM Gap 입력 -> MEDIUM task 생성"""
    gap_result = {"missing_topics": ["예시"], "priority": "MEDIUM"}
    result = generator.generate(gap_result)
    
    assert len(result["tasks"]) == 1
    assert result["tasks"][0]["priority"] == "MEDIUM"
    assert result["tasks"][0]["action"] == "계산 예시 추가"

def test_generate_no_gap(generator):
    """Test 3: Gap 없음 -> 빈 tasks 반환"""
    gap_result = {"missing_topics": [], "priority": "LOW"}
    result = generator.generate(gap_result)
    
    assert result["tasks"] == []
