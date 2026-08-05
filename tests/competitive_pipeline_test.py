# -*- coding: utf-8 -*-
"""tests/competitive_pipeline_test.py — Competitive Analysis Pipeline 통합 테스트"""
import json
import pytest
from pathlib import Path
from modules.competitive_analysis import (
    SERPCollector, MockSERPProvider, CompetitorParser, 
    TopicExtractor, ContentGapAnalyzer, ImprovementGenerator, CompetitiveValidator
)

def run_pipeline_for_calculator(keyword, our_profile):
    # 1. Collect
    collector = SERPCollector(MockSERPProvider())
    serp_data = collector.collect(keyword)
    
    # 2. Parse (Simulated competitors)
    parser = CompetitorParser()
    competitor_profiles = [parser.parse(f"## {keyword}\n## 지급 조건\n## FAQ") for _ in range(3)]
    
    # 3. Extract Topics
    extractor = TopicExtractor()
    topic_data = extractor.extract(competitor_profiles)
    
    # 4. Analyze Gap
    analyzer = ContentGapAnalyzer()
    gap_result = analyzer.analyze(our_profile, topic_data)
    
    # 5. Generate Tasks
    generator = ImprovementGenerator()
    tasks = generator.generate(gap_result)
    
    # 6. Validate
    validator = CompetitiveValidator()
    validation = validator.validate(gap_result, tasks)
    
    return {
        "keyword": keyword,
        "competitor_topics": topic_data["common_topics"],
        "our_missing_topics": gap_result["missing_topics"],
        "improvement_tasks": tasks["tasks"],
        "validation_status": validation["status"]
    }

def test_full_pipeline_integration():
    calculators = [
        ("주휴수당 계산기", {"topics": ["계산 방법"]}),
        ("육아휴직 계산기", {"topics": ["계산 방법"]}),
        ("퇴직금 계산기", {"topics": ["계산 방법"]})
    ]
    
    snapshot = []
    for keyword, profile in calculators:
        result = run_pipeline_for_calculator(keyword, profile)
        snapshot.append(result)
        assert result["validation_status"] == "PASS"

    # Save Golden Snapshot
    output_path = Path("tests/snapshots/competitive_analysis_snapshot.json")
    output_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Snapshot saved to {output_path}")
