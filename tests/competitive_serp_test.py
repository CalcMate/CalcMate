# -*- coding: utf-8 -*-
"""tests/competitive_serp_test.py — SERPCollector 통합 테스트"""
import pytest
from modules.competitive_analysis.serp_collector import SERPCollector, MockSERPProvider

@pytest.fixture
def collector():
    return SERPCollector(MockSERPProvider())

def test_collect_valid_keyword(collector):
    """1. keyword 입력 -> results 반환"""
    keyword = "주휴수당 계산기"
    result = collector.collect(keyword)
    assert "results" in result
    assert result["keyword"] == keyword

def test_collect_empty_keyword(collector):
    """2. 빈 keyword 입력 -> validation error"""
    with pytest.raises(ValueError):
        collector.collect("")

def test_collect_result_count(collector):
    """3. result 개수 확인 -> 5개 반환"""
    result = collector.collect("테스트 키워드")
    assert len(result["results"]) == 5
