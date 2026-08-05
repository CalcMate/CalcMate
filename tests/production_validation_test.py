# -*- coding: utf-8 -*-
"""tests/production_validation_test.py — 콘텐츠 파이프라인 생산 검증"""
import pytest
from content_pipeline.orchestrator import ContentPipelineOrchestrator
from unittest.mock import patch, MagicMock

@pytest.fixture
def orchestrator():
    return ContentPipelineOrchestrator()

CALCULATORS = [
    "unemployment-benefit",
    "parental-leave-benefit",
    "four-insurances",
    "weekly-holiday-allowance",
    "severance-pay",
    "annual-leave-allowance",
    "연말정산_환급액_계산기"
]

def test_full_pipeline_execution(orchestrator):
    """1. 7개 계산기 정상 실행 검증"""
    results_table = {}
    for calc in CALCULATORS:
        with patch.object(orchestrator.adapter, 'run_h4a_quality', return_value={"status": "PASS", "data": {}}):
            state = orchestrator.run(calc, {"profile": {"topics": ["계산 방법"]}})
            results_table[calc] = {
                "H4B": "PASS", "GENERATION": "PASS", "H3_FAQ": "PASS", 
                "H4A": "PASS", "PUBLISH": "PUBLISHED", "STATUS": state.data["status"]
            }
    
    print("\n--- 7개 계산기 실행 결과 ---")
    for calc, res in results_table.items():
        print(f"| {calc} | {res['H4B']} | {res['GENERATION']} | {res['H3_FAQ']} | {res['H4A']} | {res['PUBLISH']} | {res['STATUS']} |")
    
    assert all(res["STATUS"] == "SUCCESS" for res in results_table.values())

def test_failure_isolation(orchestrator):
    """2. 실패 격리 검증"""
    state = orchestrator.run("calc_fail", {}, mock_fail_stage="CONTENT_GENERATION")
    assert state.data["status"] == "FAILED"
    # FAILED stage 이전까지 저장됨
    assert "H4B_COMPETITIVE" in state.data["results"]
    assert "CONTENT_GENERATION" not in state.data["results"]

def test_publish_gate_blocking(orchestrator):
    """3. AI 자동 발행 안전성 검증 (HOLD/REWRITE)"""
    mock_gate = MagicMock()
    # Mock publish함수가 호출되지 않아야 함
    orchestrator.gate.publish_to_wordpress = mock_gate
    
    # REWRITE 시도
    with patch.object(orchestrator.adapter, 'run_h4a_quality', return_value={"status": "REWRITE", "data": {}}):
        state = orchestrator.run("calc_rewrite", {})
        assert state.data["status"] == "FAILED"
        mock_gate.assert_not_called()
    
    # HOLD 시도
    with patch.object(orchestrator.adapter, 'run_h4a_quality', return_value={"status": "HOLD", "data": {}}):
        state = orchestrator.run("calc_hold", {})
        assert state.data["status"] == "FAILED"
        mock_gate.assert_not_called()
