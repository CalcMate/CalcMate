# -*- coding: utf-8 -*-
"""tests/competitive_parser_test.py — CompetitorParser 통합 테스트"""
import pytest
from modules.competitive_analysis.competitor_parser import CompetitorParser

@pytest.fixture
def parser():
    return CompetitorParser()

def test_parse_valid_content(parser):
    content = """
    # 주휴수당 계산법
    ## 주휴수당 조건
    Q. 주휴수당은 무엇인가요?
    | 구분 | 내용 |
    |---|---|
    10000원 예시입니다.
    출처: 고용노동부
    """
    result = parser.parse(content)
    
    assert result["title"] == "주휴수당 계산법"
    assert "주휴수당 조건" in result["sections"]
    assert result["faq_count"] >= 1
    assert result["table_count"] >= 1
    assert result["example_count"] >= 1
    assert result["source_count"] >= 1
