# -*- coding: utf-8 -*-
"""tests/test_suggest_formula.py — CA-3-3: suggest_formula() 단위 테스트

실제 AI API 호출 없음 — _chat()을 monkeypatch로 mock.
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from modules.app_factory import suggest_formula

# ── 공통 mock 헬퍼 ────────────────────────────────────────────────────────────

def _mock_chat(response_text):
    """_chat() mock 반환값: (text, model, tokens)"""
    return lambda *a, **k: (response_text, "mock-model", 50)

def _mock_chat_exc(exc):
    """_chat() mock — 예외 발생"""
    def _raise(*a, **k):
        raise exc
    return _raise

CFG = {}   # 테스트용 더미 cfg


# ── TEST-1: Type A 정상 Formula 제안 ─────────────────────────────────────────

def test_type_a_success_json(monkeypatch):
    """TEST-1: Type A 단순 산술 — JSON 응답, success=True, status=ai_suggested."""
    resp = json.dumps({
        "formula": "hourly_wage * weekly_hours / 5",
        "reason": "주휴수당 기본 공식",
        "assumptions": [],
        "warnings": [],
    })
    monkeypatch.setattr("modules.app_factory._chat", _mock_chat(resp))
    result = suggest_formula(
        CFG,
        name="주휴수당 계산기",
        category="노무/급여",
        input_fields=["hourly_wage", "weekly_hours"],
        output_fields=["weekly_pay"],
    )
    assert result["success"] is True
    assert result["status"] == "ai_suggested"
    assert result["formula"] is not None
    assert result["formula"] != ""


# ── TEST-2: Type B Formula 제안 (dict formula) ────────────────────────────────

def test_type_b_dict_formula(monkeypatch):
    """TEST-2: Type B 다중 출력 — dict formula 정상 반환."""
    resp = json.dumps({
        "formula": {
            "national_pension": "monthly_salary * 0.045",
            "health_insurance": "monthly_salary * 0.03545",
        },
        "reason": "4대보험 계산",
        "assumptions": [],
        "warnings": ["요율은 매년 변경될 수 있습니다"],
    })
    monkeypatch.setattr("modules.app_factory._chat", _mock_chat(resp))
    result = suggest_formula(
        CFG,
        name="4대보험 계산기",
        input_fields=["monthly_salary"],
        output_fields=["national_pension", "health_insurance"],
    )
    assert result["success"] is True
    assert result["status"] == "ai_suggested"
    assert isinstance(result["formula"], dict)
    assert "national_pension" in result["formula"]
    assert len(result["warnings"]) > 0


# ── TEST-3: Type D 차단 (CUSTOM_COMPUTE_SLUGS) ────────────────────────────────

def test_type_d_blocked_by_custom_slug(monkeypatch):
    """TEST-3a: CUSTOM_COMPUTE_SLUGS 대상 — AI 호출 없이 차단."""
    chat_called = []
    monkeypatch.setattr("modules.app_factory._chat",
                        lambda *a, **k: chat_called.append(1) or ("", "", 0))
    result = suggest_formula(
        CFG,
        name="연말정산 계산기",
        input_fields=["gross_income"],
        output_fields=["tax_refund"],
        slug="연말정산_환급액_계산기",
    )
    assert result["success"] is False
    assert result["status"] == "not_generated"
    assert len(chat_called) == 0   # AI 호출 없음


def test_type_d_blocked_by_keyword_in_flow(monkeypatch):
    """TEST-3b: calculation_flow에 '매년 변경' 키워드 — AI 호출 없이 차단."""
    chat_called = []
    monkeypatch.setattr("modules.app_factory._chat",
                        lambda *a, **k: chat_called.append(1) or ("", "", 0))
    result = suggest_formula(
        CFG,
        name="실업급여 계산기",
        input_fields=["avg_daily_wage"],
        output_fields=["benefit"],
        calculation_flow=["상한 적용: 매년 변경(2024년 기준 1일 66,000원)"],
    )
    assert result["success"] is False
    assert result["status"] == "not_generated"
    assert len(chat_called) == 0


def test_type_d_blocked_by_table_keyword(monkeypatch):
    """TEST-3c: calculation_flow에 '별표' 키워드 — AI 호출 없이 차단."""
    chat_called = []
    monkeypatch.setattr("modules.app_factory._chat",
                        lambda *a, **k: chat_called.append(1) or ("", "", 0))
    result = suggest_formula(
        CFG,
        name="테스트",
        input_fields=["x"],
        output_fields=["y"],
        calculation_flow=["소정급여일수 = 나이·피보험기간에 따라 120~270일(고용보험법 별표)"],
    )
    assert result["success"] is False
    assert len(chat_called) == 0


# ── TEST-4: 존재하지 않는 input variable ─────────────────────────────────────

def test_invalid_input_variable(monkeypatch):
    """TEST-4: R-1 — AI가 input_fields에 없는 변수 사용 → success=False."""
    resp = json.dumps({
        "formula": "base_pay + overtime_pay",  # overtime_pay가 없음
        "reason": "기본급 + 초과근무",
        "assumptions": [],
        "warnings": [],
    })
    monkeypatch.setattr("modules.app_factory._chat", _mock_chat(resp))
    result = suggest_formula(
        CFG,
        name="급여 계산기",
        input_fields=["base_pay", "extra_pay"],   # overtime_pay 없음
        output_fields=["total_pay"],
    )
    assert result["success"] is False
    assert result["status"] == "not_generated"
    assert "overtime_pay" in result["reason"] or "overtime_pay" in str(result["warnings"])


# ── TEST-5: 존재하지 않는 output variable ────────────────────────────────────

def test_invalid_output_variable(monkeypatch):
    """TEST-5: R-2 — AI가 output_fields에 없는 키 사용(dict formula) → success=False."""
    resp = json.dumps({
        "formula": {"salary": "base_pay + extra_pay"},  # 'salary' ∉ output_fields
        "reason": "급여 합계",
        "assumptions": [],
        "warnings": [],
    })
    monkeypatch.setattr("modules.app_factory._chat", _mock_chat(resp))
    result = suggest_formula(
        CFG,
        name="급여 계산기",
        input_fields=["base_pay", "extra_pay"],
        output_fields=["total_pay"],              # 'salary' 없음
    )
    assert result["success"] is False
    assert result["status"] == "not_generated"
    assert "salary" in result["reason"] or "salary" in str(result["warnings"])


# ── TEST-6: JSON 응답 파싱 ────────────────────────────────────────────────────

def test_json_response_parsing(monkeypatch):
    """TEST-6: B형 JSON 응답이 올바르게 파싱된다."""
    resp = json.dumps({
        "formula": "base_pay * 0.033",
        "reason": "3.3% 원천징수",
        "assumptions": ["소득세 3% + 지방소득세 0.3%"],
        "warnings": ["종합소득세 신고로 정산됩니다"],
    })
    monkeypatch.setattr("modules.app_factory._chat", _mock_chat(resp))
    result = suggest_formula(
        CFG,
        name="3.3% 원천징수 계산기",
        input_fields=["base_pay"],
        output_fields=["withholding_tax"],
    )
    assert result["success"] is True
    assert result["formula"] == "base_pay * 0.033"
    assert result["reason"] == "3.3% 원천징수"
    assert len(result["assumptions"]) == 1
    assert len(result["warnings"]) == 1


# ── TEST-7: Raw string 응답 파싱 ─────────────────────────────────────────────

def test_raw_string_response_parsing(monkeypatch):
    """TEST-7: A형 raw string 응답이 formula로 처리된다."""
    monkeypatch.setattr("modules.app_factory._chat", _mock_chat("base_pay * 0.033"))
    result = suggest_formula(
        CFG,
        name="3.3% 원천징수 계산기",
        input_fields=["base_pay"],
        output_fields=["withholding_tax"],
    )
    assert result["success"] is True
    assert result["status"] == "ai_suggested"
    assert "base_pay" in str(result["formula"])


# ── TEST-8: AI 호출 실패 ──────────────────────────────────────────────────────

def test_ai_call_failure_handled(monkeypatch):
    """TEST-8: R-7 — AI 호출 예외가 외부로 전파되지 않고 실패 결과 반환."""
    monkeypatch.setattr("modules.app_factory._chat",
                        _mock_chat_exc(ConnectionError("API timeout")))
    result = suggest_formula(
        CFG,
        name="주휴수당 계산기",
        input_fields=["hourly_wage"],
        output_fields=["weekly_pay"],
    )
    assert result["success"] is False
    assert result["status"] == "not_generated"
    assert result["formula"] is None
    assert "API timeout" in result["reason"] or "API timeout" in str(result["warnings"])


# ── TEST-9: 빈 AI 응답 ────────────────────────────────────────────────────────

def test_empty_ai_response_handled(monkeypatch):
    """TEST-9: R-8 — 빈 응답이 안전하게 실패 처리된다."""
    for empty in ["", "   ", None]:
        monkeypatch.setattr("modules.app_factory._chat", _mock_chat(empty or ""))
        result = suggest_formula(
            CFG,
            name="주휴수당 계산기",
            input_fields=["hourly_wage"],
            output_fields=["weekly_pay"],
        )
        assert result["success"] is False
        assert result["status"] == "not_generated"
        assert result["formula"] is None


# ── TEST-10: status 확인 ──────────────────────────────────────────────────────

def test_success_status_is_ai_suggested_not_operator_confirmed(monkeypatch):
    """TEST-10: AI 제안 성공 시 status='ai_suggested' — 절대 'operator_confirmed' 아님."""
    resp = json.dumps({
        "formula": "daily_wage * unused_days",
        "reason": "연차수당 공식",
        "assumptions": [],
        "warnings": [],
    })
    monkeypatch.setattr("modules.app_factory._chat", _mock_chat(resp))
    result = suggest_formula(
        CFG,
        name="연차수당 계산기",
        input_fields=["daily_wage", "unused_days"],
        output_fields=["leave_allowance"],
    )
    assert result["success"] is True
    assert result["status"] == "ai_suggested"
    assert result["status"] != "operator_confirmed"
    assert result["status"] != "pending_validation"


# ── TEST-11: 기존 Formula 자동 overwrite 없음 ─────────────────────────────────

def test_suggest_formula_does_not_modify_external_state(monkeypatch):
    """TEST-11: R-6 — suggest_formula()가 외부 상태(기존 formula)를 직접 변경하지 않음."""
    resp = json.dumps({
        "formula": "base_pay * 1.1",
        "reason": "10% 추가",
        "assumptions": [],
        "warnings": [],
    })
    monkeypatch.setattr("modules.app_factory._chat", _mock_chat(resp))

    existing_formula = "base_pay * 1.0"
    result = suggest_formula(
        CFG,
        name="급여 계산기",
        input_fields=["base_pay"],
        output_fields=["total_pay"],
    )
    # 함수 반환값으로 새 formula 제공되지만 기존 변수는 변경 없음
    assert existing_formula == "base_pay * 1.0"   # 외부 상태 유지
    assert result["formula"] != existing_formula  # 제안값은 다름
    assert result["success"] is True


# ── 추가: input_fields 없을 때 안전 처리 ─────────────────────────────────────

def test_missing_input_fields_returns_failure(monkeypatch):
    """input_fields가 없으면 AI 호출 없이 실패 반환."""
    chat_called = []
    monkeypatch.setattr("modules.app_factory._chat",
                        lambda *a, **k: chat_called.append(1) or ("x", "m", 0))
    result = suggest_formula(CFG, name="테스트", input_fields=[], output_fields=["y"])
    assert result["success"] is False
    assert len(chat_called) == 0


def test_missing_output_fields_returns_failure(monkeypatch):
    """output_fields가 없으면 AI 호출 없이 실패 반환."""
    chat_called = []
    monkeypatch.setattr("modules.app_factory._chat",
                        lambda *a, **k: chat_called.append(1) or ("x", "m", 0))
    result = suggest_formula(CFG, name="테스트", input_fields=["x"], output_fields=[])
    assert result["success"] is False
    assert len(chat_called) == 0


# ── 추가: null formula 반환 처리 ─────────────────────────────────────────────

def test_ai_returns_null_formula(monkeypatch):
    """AI가 formula=null을 반환하면 success=False."""
    resp = json.dumps({
        "formula": None,
        "reason": "계산 근거가 불충분합니다",
        "assumptions": [],
        "warnings": ["calculation_flow 없음"],
    })
    monkeypatch.setattr("modules.app_factory._chat", _mock_chat(resp))
    result = suggest_formula(
        CFG,
        name="테스트",
        input_fields=["x"],
        output_fields=["y"],
    )
    assert result["success"] is False
    assert result["formula"] is None


# ── 추가: dict formula 키가 output_fields의 부분집합인 경우 허용 ───────────────

def test_dict_formula_subset_of_output_fields_allowed(monkeypatch):
    """dict formula 키가 output_fields의 일부인 경우 허용 (부분집합 OK)."""
    resp = json.dumps({
        "formula": {"national_pension": "monthly_salary * 0.045"},
        "reason": "국민연금만",
        "assumptions": [],
        "warnings": [],
    })
    monkeypatch.setattr("modules.app_factory._chat", _mock_chat(resp))
    result = suggest_formula(
        CFG,
        name="4대보험 계산기",
        input_fields=["monthly_salary"],
        output_fields=["national_pension", "health_insurance"],  # 2개지만 AI는 1개만 반환
    )
    assert result["success"] is True
    assert "national_pension" in result["formula"]


# ── 추가: calculation_flow에 Type D 키워드 없으면 정상 진행 ──────────────────

def test_type_a_flow_no_type_d_keywords_passes(monkeypatch):
    """Type A flow — Type D 키워드 없으면 AI 호출 진행."""
    resp = json.dumps({
        "formula": "hourly_wage * weekly_hours / 5",
        "reason": "주휴수당",
        "assumptions": [],
        "warnings": [],
    })
    monkeypatch.setattr("modules.app_factory._chat", _mock_chat(resp))
    result = suggest_formula(
        CFG,
        name="주휴수당 계산기",
        input_fields=["hourly_wage", "weekly_hours"],
        output_fields=["weekly_holiday_pay"],
        calculation_flow=["주휴수당 = 1일 소정근로시간 × 시급"],  # Type D 키워드 없음
    )
    assert result["success"] is True
    assert result["status"] == "ai_suggested"
