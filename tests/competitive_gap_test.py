# -*- coding: utf-8 -*-
"""tests/competitive_gap_test.py — ContentGapAnalyzer 테스트"""
import pytest
from modules.competitive_analysis.content_gap_analyzer import ContentGapAnalyzer

@pytest.fixture
def analyzer():
    return ContentGapAnalyzer()

def test_gap_analysis_essential_missing(analyzer):
    """Test 1: 필수 Topic 존재, 누락 시 HIGH"""
    our_profile = {"topics": ["계산 방법"]}
    competitor_topics = {"common_topics": ["계산 방법", "FAQ"]}
    
    result = analyzer.analyze(our_profile, competitor_topics)
    
    assert "FAQ" in result["missing_topics"]
    assert result["priority"] == "HIGH"

def test_gap_analysis_all_present(analyzer):
    """Test 2: 모든 Topic 존재"""
    our_profile = {"topics": ["계산 방법", "FAQ"]}
    competitor_topics = {"common_topics": ["계산 방법", "FAQ"]}
    
    result = analyzer.analyze(our_profile, competitor_topics)
    
    assert result["missing_topics"] == []
    assert result["priority"] == "LOW"

def test_gap_analysis_empty(analyzer):
    """Test 3: 빈 데이터"""
    our_profile = {}
    competitor_topics = {}
    
    result = analyzer.analyze(our_profile, competitor_topics)
    
    assert result["missing_topics"] == []
    assert result["priority"] == "LOW"
