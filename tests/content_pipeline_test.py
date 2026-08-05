# -*- coding: utf-8 -*-
"""tests/content_pipeline_test.py — Pipeline 테스트"""
import pytest
import json
from pathlib import Path
from unittest.mock import patch
from content_pipeline.orchestrator import ContentPipelineOrchestrator

@pytest.fixture
def orchestrator():
    return ContentPipelineOrchestrator()

def test_pipeline_success(orchestrator):
    """Test 1: 정상 Pipeline 실행"""
    with patch.object(orchestrator.adapter, 'run_h4a_quality', return_value={"status": "PASS", "data": {}}), \
         patch.object(orchestrator.gate.publisher, 'create_draft', return_value="123"):
        state = orchestrator.run("calc1", {})
        assert state.data["status"] == "SUCCESS"
        assert len(state.data["results"]) >= 4 # H4B, CONTENT, H3, H4A

def test_pipeline_failure(orchestrator):
    """Test 2: 중간 stage 실패"""
    state = orchestrator.run("calc1", {}, mock_fail_stage="H3_FAQ")
    assert state.data["status"] == "FAILED"
    assert "Stage H3_FAQ failed" in state.data["errors"]
    assert "H3_FAQ" not in state.data["results"]

def test_pipeline_log_saved(orchestrator):
    """Test 3: state 저장 확인"""
    calc_id = "calc2"
    orchestrator.run(calc_id, {}, mock_fail_stage="CONTENT_GENERATION")
    
    log_file = Path("logs/content_pipeline") / f"pipeline_p_{calc_id}.json"
    assert log_file.exists()
    
    with open(log_file, "r", encoding="utf-8") as f:
        log_data = json.load(f)
        assert log_data["status"] == "FAILED"
        assert "CONTENT_GENERATION" in log_data["current_stage"]
