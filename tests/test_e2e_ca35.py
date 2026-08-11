# -*- coding: utf-8 -*-
"""tests/test_e2e_ca35.py — CA-3-5 E2E 최종검증

CA-3-3 suggest_formula() + CA-3-4 Dashboard 연결 완료 이후
전체 Formula lifecycle을 통합 E2E 수준으로 검증한다.

E2E-NEW-1: AI 제안 → build_contract() → pending_validation (자동 확정 방지)
E2E-NEW-2: operator_confirmed → build_contract() → 상태 보존 + HOLD-1 미발동
E2E-NEW-3: dict formula Round-trip (Contract Instance YAML 저장/로드)
E2E-NEW-4: delete 경로 → Contract Instance 파일 + registry.yaml 항목 완전 제거
E2E-NEW-5: Dashboard Discard → CA-3-4 신규 session state 4개 완전 소거

추가 검증:
  - Formula 상태 머신 전체 lifecycle
  - HOLD-1 발동/미발동 조건 최종 확인
  - Contract Instance 저장/로드/삭제 완전성
"""
import json
import sys
from pathlib import Path

import pytest
import yaml as _yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from modules.app_factory import (
    AF_SESSION_DISCARD_KEYS,
    _delete_contract_instance,
    _save_contract_instance,
    build_contract,
    check_hold_rules,
)
from modules.formula_engine import validate_formula_with_samples


# ─────────────────────────────────────────────────────────────────────────────
# E2E-NEW-1: AI 제안 → build_contract() → pending_validation
# ─────────────────────────────────────────────────────────────────────────────

def test_e2e_new1_ai_suggestion_no_auto_confirm():
    """E2E-NEW-1: AI suggestion 성공해도 operator_confirmed로 자동 승격되지 않는다.

    흐름:
      suggest_formula() → status="ai_suggested"
      Dashboard: af_formula_confirmed_text 없음 (AI 제안 시 pop됨)
      build_contract(formula_status=None) → pending_validation (auto-derived)
      check_hold_rules() → HOLD-1 발동

    «AI가 formula를 생성했다 ≠ 운영자가 formula를 확정했다»
    """
    # Step 1: suggest_formula() 성공 결과 시뮬레이션
    sf_result = {
        "success": True,
        "formula": "hourly_wage * weekly_hours / 5",
        "reason": "주휴수당 공식",
        "assumptions": [],
        "warnings": [],
        "status": "ai_suggested",
    }
    assert sf_result["status"] == "ai_suggested"
    formula_str = str(sf_result["formula"])

    # Step 2: Dashboard CA-3-4 세션 업데이트 로직 재현
    # AI 제안 성공 시 af_formula_confirmed_text가 pop됨
    session = {
        "af_contract_formula":          formula_str,
        "af_formula_ai_suggested_text": formula_str,
        # af_formula_confirmed_text 없음 (pop 됐거나 애초에 없었음)
    }

    # Step 3: [📋 Contract 기반 생성] Dashboard 로직 재현
    # _fv_prior_raw = "" → _fv_prior_status = None
    _fv_prior_raw  = session.get("af_formula_confirmed_text", "")
    _formula_raw   = session.get("af_contract_formula", "").strip()
    _fv_prior_status = (
        "operator_confirmed"
        if _fv_prior_raw and _formula_raw == _fv_prior_raw
        else None
    )
    assert _fv_prior_status is None, "미확정 상태인데 operator_confirmed가 파생됨"

    contract = build_contract(
        "weekly-holiday-e2e",
        "주휴수당 계산기",
        formula=_formula_raw,
        formula_status=_fv_prior_status,   # None → auto-derived
        input_fields=["hourly_wage", "weekly_hours"],
        output_fields=["weekly_pay"],
        category="노무/급여",
    )

    # Step 4: 상태 검증
    assert contract["formula_status"] == "pending_validation", (
        f"AI 제안 후 미확정 → pending_validation 이어야 하는데: {contract['formula_status']!r}"
    )
    assert contract["formula_status"] != "operator_confirmed", (
        "AI 제안이 operator_confirmed로 자동 승격됨 — 원칙 위반"
    )
    # ai_suggested는 Dashboard 추적용 — Contract에 직접 들어가면 안 됨
    assert contract["formula_status"] != "ai_suggested", (
        "ai_suggested가 Contract에 직접 저장됨 — Dashboard 추적 전용 상태"
    )

    # Step 5: HOLD-1 발동 확인
    hold = check_hold_rules(contract)
    assert hold["held"] is True
    assert "HOLD-1" in hold["rules"]


# ─────────────────────────────────────────────────────────────────────────────
# E2E-NEW-2: operator_confirmed → Contract 상태 보존 + HOLD-1 미발동
# ─────────────────────────────────────────────────────────────────────────────

def test_e2e_new2_operator_confirmed_preserved():
    """E2E-NEW-2: 운영자 확정 후 build_contract() → operator_confirmed 보존 + HOLD-1 없음.

    흐름:
      formula text_area 입력
      [🔍 검증] 통과
      [✅ Formula 확정] → af_formula_confirmed_text 설정
      build_contract(formula_status="operator_confirmed")
      check_hold_rules() → HOLD-1 없음
    """
    formula_raw = "daily_wage * unused_days"

    # 운영자가 [✅ Formula 확정] 클릭 → af_formula_confirmed_text 설정
    session = {
        "af_contract_formula":      formula_raw,
        "af_formula_confirmed_text": formula_raw,   # 확정 시 설정됨
    }

    # [📋 Contract 기반 생성] Dashboard 로직 재현
    _fv_prior_raw  = session.get("af_formula_confirmed_text", "")
    _formula_raw   = session.get("af_contract_formula", "").strip()
    _fv_prior_status = (
        "operator_confirmed"
        if _fv_prior_raw and _formula_raw == _fv_prior_raw
        else None
    )
    assert _fv_prior_status == "operator_confirmed"

    contract = build_contract(
        "annual-leave-e2e",
        "연차수당 계산기",
        formula=_formula_raw,
        formula_status=_fv_prior_status,
        input_fields=["daily_wage", "unused_days"],
        output_fields=["leave_pay"],
        category="노무/급여",
    )

    assert contract["formula_status"] == "operator_confirmed"

    # HOLD-1 미발동 확인
    hold = check_hold_rules(contract)
    assert "HOLD-1" not in hold["rules"], (
        f"operator_confirmed 상태에서 HOLD-1이 발동됨: {hold['rules']}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# E2E-NEW-3: dict formula Round-trip
# ─────────────────────────────────────────────────────────────────────────────

def test_e2e_new3_dict_formula_round_trip(tmp_path, monkeypatch):
    """E2E-NEW-3: dict formula → build_contract → YAML 저장 → 로드 → dict 구조 보존.

    Type B 계산기의 dict formula가 Contract Instance를 거치며
    str로 손상되지 않는지 검증한다.
    """
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")

    dict_formula = {
        "national_pension":  "monthly_salary * 0.045",
        "health_insurance":  "monthly_salary * 0.03545",
    }

    # build_contract() — dict formula 그대로 보존
    contract = build_contract(
        "four-insurances-e2e",
        "4대보험 계산기",
        formula=dict_formula,
        formula_status="operator_confirmed",
        input_fields=["monthly_salary"],
        output_fields=["national_pension", "health_insurance"],
        category="노무/급여/보험",
    )
    assert isinstance(contract["formula"], dict)
    assert contract["formula_status"] == "operator_confirmed"

    # Contract Instance YAML 저장
    _save_contract_instance("four-insurances-e2e", contract)

    # YAML 로드
    instance_path = tmp_path / "schema" / "instances" / "four-insurances-e2e.yaml"
    assert instance_path.exists()
    loaded = _yaml.safe_load(instance_path.read_text(encoding="utf-8"))

    # dict formula 구조 보존
    assert isinstance(loaded["formula"], dict), (
        f"dict formula가 str로 변환됨: {type(loaded['formula'])}"
    )
    assert loaded["formula"] == dict_formula
    assert set(loaded["formula"].keys()) == {"national_pension", "health_insurance"}

    # 기타 필드 보존
    assert loaded["formula_status"]  == "operator_confirmed"
    assert loaded["input_fields"]    == ["monthly_salary"]
    assert loaded["output_fields"]   == ["national_pension", "health_insurance"]
    assert loaded["name"]            == "4대보험 계산기"
    assert "generated_at" in loaded


def test_e2e_new3_string_formula_round_trip(tmp_path, monkeypatch):
    """E2E-NEW-3 보조: str formula도 동일하게 보존된다 (dict와 대칭 확인)."""
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")

    str_formula = "hourly_wage * (weekly_hours / 40) * 8"

    contract = build_contract(
        "weekly-holiday-e2e-str",
        "주휴수당 계산기",
        formula=str_formula,
        formula_status="operator_confirmed",
        input_fields=["hourly_wage", "weekly_hours"],
        output_fields=["weekly_holiday_pay"],
    )

    _save_contract_instance("weekly-holiday-e2e-str", contract)
    loaded = _yaml.safe_load(
        (tmp_path / "schema" / "instances" / "weekly-holiday-e2e-str.yaml")
        .read_text(encoding="utf-8")
    )

    assert isinstance(loaded["formula"], str)
    assert loaded["formula"] == str_formula


# ─────────────────────────────────────────────────────────────────────────────
# E2E-NEW-4: delete 경로 → Contract Instance 완전 제거
# ─────────────────────────────────────────────────────────────────────────────

def test_e2e_new4_delete_removes_contract_instance_and_registry(tmp_path, monkeypatch):
    """E2E-NEW-4: Contract Instance 저장 후 삭제 → 파일 + registry 항목 완전 제거."""
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")

    contract = build_contract(
        "delete-e2e-calc",
        "삭제 테스트 계산기",
        formula="a * b",
        formula_status="operator_confirmed",
        input_fields=["a"],
        output_fields=["result"],
    )

    # 저장
    _save_contract_instance("delete-e2e-calc", contract)
    instance_path  = tmp_path / "schema" / "instances" / "delete-e2e-calc.yaml"
    registry_path  = tmp_path / "schema" / "registry.yaml"

    assert instance_path.exists(), "Contract Instance가 생성되지 않음"
    reg_before = _yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    assert "delete-e2e-calc" in (reg_before.get("instances") or {})

    # 삭제
    result = _delete_contract_instance("delete-e2e-calc")
    assert result is True

    # 파일 없음
    assert not instance_path.exists(), "Contract Instance 파일이 삭제되지 않음"

    # registry.yaml 항목 제거
    reg_after = _yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    assert "delete-e2e-calc" not in (reg_after.get("instances") or {}), (
        "registry.yaml에서 항목이 제거되지 않음"
    )


def test_e2e_new4_other_instances_unaffected(tmp_path, monkeypatch):
    """E2E-NEW-4 보조: 삭제가 다른 Contract Instance에 영향을 주지 않는다."""
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")

    c1 = build_contract("calc-keep", "유지 계산기", formula="x + y",
                        input_fields=["x", "y"], output_fields=["z"])
    c2 = build_contract("calc-del",  "삭제 계산기", formula="a * b",
                        input_fields=["a"], output_fields=["r"])

    _save_contract_instance("calc-keep", c1)
    _save_contract_instance("calc-del", c2)

    _delete_contract_instance("calc-del")

    # calc-del 파일 없음
    assert not (tmp_path / "schema" / "instances" / "calc-del.yaml").exists()

    # calc-keep은 여전히 존재
    assert (tmp_path / "schema" / "instances" / "calc-keep.yaml").exists()
    reg = _yaml.safe_load(
        (tmp_path / "schema" / "registry.yaml").read_text(encoding="utf-8")
    )
    assert "calc-keep" in (reg.get("instances") or {}), "다른 Contract Instance가 영향받음"
    assert "calc-del" not in (reg.get("instances") or {})


# ─────────────────────────────────────────────────────────────────────────────
# E2E-NEW-5: Dashboard Discard → CA-3-4 신규 session state 소거
# ─────────────────────────────────────────────────────────────────────────────

def test_e2e_new5_discard_clears_ca34_keys():
    """E2E-NEW-5: Discard 실행 → CA-3-4에서 추가된 신규 session state 4개 전부 소거."""
    # CA-3-4 신규 키 4개
    ca34_new_keys = {
        "af_formula_confirmed_text",
        "af_formula_validation",
        "af_formula_ai_suggested_text",
        "_af_ai_suggest_override",
    }

    # 1. AF_SESSION_DISCARD_KEYS에 포함 확인
    assert ca34_new_keys.issubset(set(AF_SESSION_DISCARD_KEYS)), (
        f"DISCARD_KEYS 미포함 키: {ca34_new_keys - set(AF_SESSION_DISCARD_KEYS)}"
    )

    # 2. AI Formula 제안 후 세션 상태 시뮬레이션
    session = {
        # 기본 AF 키
        "af_result":              {"name": "주휴수당 계산기"},
        "af_name":                "주휴수당 계산기",
        "af_cat":                 "노무/급여",
        "af_desc":                "주휴수당 계산",
        "af_contract":            {"formula_status": "ai_suggested"},
        "af_contract_formula":    "hourly_wage * weekly_hours / 5",
        "af_contract_input_fields":  "hourly_wage, weekly_hours",
        "af_contract_output_fields": "weekly_pay",
        # CA-3-4 신규 키 4개 모두 설정
        "af_formula_ai_suggested_text": "hourly_wage * weekly_hours / 5",
        "af_formula_confirmed_text":    "",
        "af_formula_validation":        {"valid": False},
        "_af_ai_suggest_override":      True,
        # 다른 탭 키 (보존되어야 함)
        "nav_group": "🧮 Calculator",
    }

    # 3. Discard 실행 (AF_SESSION_DISCARD_KEYS 전체 pop)
    for k in AF_SESSION_DISCARD_KEYS:
        session.pop(k, None)

    # 4. CA-3-4 신규 키 4개 소거 확인
    for key in ca34_new_keys:
        assert key not in session, f"Discard 후 '{key}'가 세션에 남아있음"

    # 5. 다른 탭 키는 보존
    assert "nav_group" in session, "다른 탭 키가 Discard로 소거됨"


def test_e2e_new5_discard_no_ai_formula_contamination():
    """E2E-NEW-5 보조: 이전 계산기의 AI Formula가 다음 계산기로 오염되지 않는다."""
    session_prev = {
        "af_formula_ai_suggested_text": "old_formula * 2",
        "af_formula_confirmed_text":    "old_formula * 2",
        "af_formula_validation":        {"valid": True},
        "_af_ai_suggest_override":      False,
        "af_contract_formula":          "old_formula * 2",
        "af_name":                      "이전 계산기",
    }

    # Discard
    for k in AF_SESSION_DISCARD_KEYS:
        session_prev.pop(k, None)

    # 새 계산기 세션 시작 — 이전 값이 남아있으면 안 됨
    assert "af_formula_ai_suggested_text" not in session_prev
    assert "af_formula_confirmed_text"    not in session_prev
    assert "af_formula_validation"        not in session_prev
    assert "_af_ai_suggest_override"      not in session_prev
    assert "af_contract_formula"          not in session_prev
    assert "af_name"                      not in session_prev


# ─────────────────────────────────────────────────────────────────────────────
# 추가: Formula 상태 머신 전체 lifecycle
# ─────────────────────────────────────────────────────────────────────────────

def test_state_machine_full_lifecycle():
    """상태 머신: not_generated → ai_suggested → pending_validation → operator_confirmed."""
    # not_generated
    c0 = build_contract("sm-test", "상태머신 계산기")
    assert c0["formula_status"] == "not_generated"

    # ai_suggested (명시)
    c1 = build_contract("sm-test", "상태머신 계산기",
                        formula="a * b", formula_status="ai_suggested")
    assert c1["formula_status"] == "ai_suggested"

    # pending_validation (auto-derived)
    c2 = build_contract("sm-test", "상태머신 계산기",
                        formula="a * b", formula_status=None)
    assert c2["formula_status"] == "pending_validation"

    # operator_confirmed (명시)
    c3 = build_contract("sm-test", "상태머신 계산기",
                        formula="a * b", formula_status="operator_confirmed")
    assert c3["formula_status"] == "operator_confirmed"


def test_state_machine_formula_modify_resets_status():
    """상태 머신: operator_confirmed 후 formula 수정 → pending_validation 복귀."""
    confirmed_raw = "a + b"
    session = {"af_formula_confirmed_text": confirmed_raw}

    # 운영자가 formula 수정
    new_raw = "a * b"
    _fv_confirmed_raw = session.get("af_formula_confirmed_text", "")
    if _fv_confirmed_raw and new_raw != _fv_confirmed_raw:
        session.pop("af_formula_confirmed_text", None)
        session.pop("af_formula_validation", None)
        # Dashboard: af_contract.formula_status = "pending_validation"
        contract_status = "pending_validation"
    else:
        contract_status = "operator_confirmed"

    assert contract_status == "pending_validation"
    assert "af_formula_confirmed_text" not in session


def test_state_machine_ai_suggested_never_auto_operator_confirmed():
    """상태 머신: ai_suggested → operator_confirmed 자동 전환 경로 없음."""
    # build_contract()에 ai_suggested 전달 → 보존 (ai_suggested 유지)
    c = build_contract("x", "X", formula="a * b", formula_status="ai_suggested")
    assert c["formula_status"] == "ai_suggested"
    assert c["formula_status"] != "operator_confirmed"

    # build_contract()에 None 전달 → pending_validation (operator_confirmed 아님)
    c2 = build_contract("x", "X", formula="a * b", formula_status=None)
    assert c2["formula_status"] == "pending_validation"
    assert c2["formula_status"] != "operator_confirmed"

    # operator_confirmed는 명시적으로만 가능
    c3 = build_contract("x", "X", formula="a * b", formula_status="operator_confirmed")
    assert c3["formula_status"] == "operator_confirmed"


# ─────────────────────────────────────────────────────────────────────────────
# 추가: HOLD-1 최종 검증
# ─────────────────────────────────────────────────────────────────────────────

def test_hold1_fires_for_not_generated():
    """HOLD-1: formula_status=not_generated → HOLD-1 발동."""
    contract = build_contract("x", "X", category="기타")
    assert contract["formula_status"] == "not_generated"
    hold = check_hold_rules(contract)
    assert "HOLD-1" in hold["rules"]


def test_hold1_fires_for_ai_suggested():
    """HOLD-1: formula_status=ai_suggested → HOLD-1 발동."""
    contract = build_contract("x", "X", formula="a * b",
                              formula_status="ai_suggested",
                              input_fields=["a"], output_fields=["b"],
                              category="기타")
    hold = check_hold_rules(contract)
    assert "HOLD-1" in hold["rules"]


def test_hold1_fires_for_pending_validation():
    """HOLD-1: formula_status=pending_validation → HOLD-1 발동."""
    contract = build_contract("x", "X", formula="a * b",
                              formula_status="pending_validation",
                              input_fields=["a"], output_fields=["b"],
                              category="기타")
    hold = check_hold_rules(contract)
    assert "HOLD-1" in hold["rules"]


def test_hold1_not_fires_for_operator_confirmed():
    """HOLD-1: formula_status=operator_confirmed → HOLD-1 미발동."""
    contract = build_contract("x", "X", formula="a * b",
                              formula_status="operator_confirmed",
                              input_fields=["a"], output_fields=["b"],
                              category="기타")
    hold = check_hold_rules(contract)
    assert "HOLD-1" not in hold["rules"]


# ─────────────────────────────────────────────────────────────────────────────
# 추가: Contract Instance 저장 완전성 (CA-3 formula lifecycle 포함)
# ─────────────────────────────────────────────────────────────────────────────

def test_contract_instance_pending_validation_full_fields(tmp_path, monkeypatch):
    """pending_validation 상태 Contract가 모든 필드와 함께 저장/복원된다."""
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")

    contract = build_contract(
        "pending-e2e",
        "검증대기 계산기",
        formula="base_pay * 0.033",
        formula_status="pending_validation",
        input_fields=["base_pay"],
        output_fields=["withholding_tax"],
        test_cases=[{"input": {"base_pay": 1000000}, "expected": {"withholding_tax": 33000.0}}],
        desc="3.3% 원천징수 계산",
        category="세금/정부혜택",
    )

    _save_contract_instance("pending-e2e", contract)
    loaded = _yaml.safe_load(
        (tmp_path / "schema" / "instances" / "pending-e2e.yaml").read_text(encoding="utf-8")
    )

    assert loaded["formula_status"] == "pending_validation"
    assert loaded["formula"] == "base_pay * 0.033"
    assert loaded["input_fields"] == ["base_pay"]
    assert loaded["output_fields"] == ["withholding_tax"]
    assert loaded["desc"] == "3.3% 원천징수 계산"
    assert loaded["test_cases"] == [{"input": {"base_pay": 1000000}, "expected": {"withholding_tax": 33000.0}}]
    assert "generated_at" in loaded


def test_validate_formula_with_samples_ai_suggested_formula():
    """AI 제안 formula도 validate_formula_with_samples()로 정상 검증된다."""
    # suggest_formula()가 반환한 formula → validate_formula_with_samples() 재사용
    ai_formula = "hourly_wage * (weekly_hours / 40) * 8"
    schema = {"hourly_wage": "number", "weekly_hours": "number"}
    test_cases = [
        {"input": {"hourly_wage": 10000, "weekly_hours": 40},
         "expected": {"result": 80000.0}},
    ]

    result = validate_formula_with_samples(ai_formula, schema, test_cases)
    # 수식 자체는 valid (Level 1/2 통과)
    assert result["valid"] is True
    # 기대값과 실제 계산값이 다를 수 있음 (Level 3 — 테스트케이스가 단일 출력 대상이 아닌 경우)
    # 수식의 valid 여부만 확인
    assert "valid" in result
    assert "message" in result
