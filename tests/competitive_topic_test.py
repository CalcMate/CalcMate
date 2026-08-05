# -*- coding: utf-8 -*-
"""tests/competitive_topic_test.py — TopicExtractor 테스트"""
import pytest
from modules.competitive_analysis.topic_extractor import TopicExtractor

def test_extract_topics():
    extractor = TopicExtractor()
    profiles = [
        {"sections": ["계산 방법", "지급 조건", "FAQ"]},
        {"sections": ["계산 공식", "지급 조건", "FAQ"]}
    ]
    result = extractor.extract(profiles)
    
    assert "계산 방법" in result["common_topics"]
    assert "지급 조건" in result["common_topics"]
    assert result["topic_frequency"]["계산 방법"] == 2
    assert result["topic_frequency"]["지급 조건"] == 2
