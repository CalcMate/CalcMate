# -*- coding: utf-8 -*-
"""tests/test_formula_contract.py — Layer 2: Formula Contract Tests

Layer 1(기존 292개): JS compute 로직(경계값·법령) — DB formula 무관
Layer 2(이 파일):    formula 표현/검증 계약 — validate_formula() / validate_compute_handler()

분리 규칙:
  formula  타입: validate_formula(formula, schema, slug)가 True를 반환해야 한다.
  custom   타입: validate_compute_handler(slug)가 True를 반환해야 한다.
             (formula="" 이므로 formula 검증을 호출하지 않는다.)

이 테스트는 DB 연결 없이 실행된다.
formula/schema 는 DB 정규화 후의 기대값을 하드코딩한다.
DB 값이 변경됐을 때 이 파일도 동기화해야 한다.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from modules.formula_engine import (
    CUSTOM_COMPUTE_SLUGS,
    validate_compute_handler,
    validate_formula,
)

# ── formula 타입 계약 ──────────────────────────────────────────────────────────
# (slug, formula, input_schema)
# formula는 DB 정규화 후 기대값. slug는 참조용(validate_formula에 전달하지 않음).
FORMULA_CONTRACTS = [
    (
        "weekly-holiday-allowance",
        "hourly_wage * (weekly_hours / 40) * 8",
        {"weekly_hours": "number", "hourly_wage": "number"},
    ),
    (
        "severance-pay",
        "avg_monthly_wage * (total_days / 365)",
        {"avg_monthly_wage": "number", "start_date": "date",
         "end_date": "date", "total_days": "number"},
    ),
    (
        "annual-leave-allowance",
        "daily_wage * unused_days",
        {"daily_wage": "number", "unused_days": "number"},
    ),
    (
        "unemployment-benefit",
        "avg_daily_wage * 0.6",
        {"avg_daily_wage": "number", "age": "number", "employment_months": "number"},
    ),
    (
        "four-insurances",
        json.dumps({
            "national_pension":     "monthly_salary * 0.045",
            "health_insurance":     "monthly_salary * 0.03545",
            "employment_insurance": "monthly_salary * 0.009",
            "total": "monthly_salary * 0.045 + monthly_salary * 0.03545 * 1.1296 + monthly_salary * 0.009",
        }, ensure_ascii=False),
        {"monthly_salary": "number"},
    ),
]


@pytest.mark.parametrize("slug, formula, schema", FORMULA_CONTRACTS,
                         ids=[c[0] for c in FORMULA_CONTRACTS])
def test_formula_type_contract(slug, formula, schema):
    """formula 타입 계산기: validate_formula가 True를 반환해야 한다."""
    ok, msg = validate_formula(formula, schema)
    assert ok, f"[{slug}] validate_formula FAIL: {msg}"


# ── custom 타입 계약 ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("slug", sorted(CUSTOM_COMPUTE_SLUGS))
def test_custom_type_handler_exists(slug):
    """custom 타입 계산기: _compute_js 핸들러가 실질적인 JS를 생성해야 한다."""
    ok, msg = validate_compute_handler(slug)
    assert ok, f"[{slug}] compute handler FAIL: {msg}"


def test_custom_type_skips_formula_validation():
    """slug 전달 시 CUSTOM_COMPUTE_SLUGS는 formula='' 도 PASS를 반환해야 한다."""
    for slug in CUSTOM_COMPUTE_SLUGS:
        ok, msg = validate_formula("", {}, slug=slug)
        assert ok, f"[{slug}] custom slug가 formula='' 에서 FAIL: {msg}"


def test_formula_type_rejects_empty_formula():
    """formula 타입 계산기: slug 없이 formula='' 는 FAIL이어야 한다."""
    ok, _ = validate_formula("", {"x": "number"})
    assert not ok, "빈 formula가 PASS를 반환했다 — 의도하지 않은 동작"


def test_formula_type_rejects_korean_text():
    """formula 타입 계산기: 한글 설명 텍스트는 FAIL이어야 한다."""
    ok, msg = validate_formula("daily_wage × unused_days", {"daily_wage": "number", "unused_days": "number"})
    assert not ok, "한글/특수문자 수식이 PASS를 반환했다"
    assert "×" in msg or "invalid" in msg.lower() or "character" in msg.lower()


def test_dict_formula_json_string_parses_correctly():
    """JSON 문자열로 저장된 dict 수식이 validate_formula에서 정상 파싱되어야 한다."""
    formula_str = json.dumps({
        "national_pension": "monthly_salary * 0.045",
        "total": "monthly_salary * 0.045",
    })
    ok, msg = validate_formula(formula_str, {"monthly_salary": "number"})
    assert ok, f"JSON dict 문자열 파싱 실패: {msg}"


# ── HOLD-3 수정: 내장 함수명 오탐 방지 ────────────────────────────────────────

def test_min_max_in_formula_passes_validation():
    """min/max를 포함한 formula는 PASS해야 한다 (HOLD-3 버그 수정 검증)."""
    formula = "15 + min(max(0, (years_of_service - 1) // 2), 10)"
    schema = {"years_of_service": "number"}
    ok, msg = validate_formula(formula, schema)
    assert ok, f"min/max 포함 formula가 FAIL: {msg}"


def test_min_max_dict_formula_passes_validation():
    """min/max가 포함된 dict formula도 PASS해야 한다."""
    formula_dict = {
        "total_days": "15 + min(max(0, (years_of_service - 1) // 2), 10)",
        "remaining_days": "15 + min(max(0, (years_of_service - 1) // 2), 10) - used_days",
    }
    schema = {"years_of_service": "number", "used_days": "number"}
    ok, msg = validate_formula(formula_dict, schema)
    assert ok, f"min/max dict formula가 FAIL: {msg}"


def test_abs_round_int_in_formula_pass_validation():
    """abs/round/int 등 허용 함수를 포함한 formula도 PASS해야 한다."""
    cases = [
        ("abs(x - y)", {"x": "number", "y": "number"}),
        ("round(a * 0.033, 2)", {"a": "number"}),
        ("int(months // 12)", {"months": "number"}),
    ]
    for expr, schema in cases:
        ok, msg = validate_formula(expr, schema)
        assert ok, f"'{expr}'가 FAIL: {msg}"


def test_undeclared_variable_still_fails():
    """input_schema에 없는 실제 변수는 여전히 FAIL이어야 한다 (과잉 관대화 방지)."""
    ok, msg = validate_formula("a * undeclared_var", {"a": "number"})
    assert not ok, "미선언 변수가 PASS됨 — 과잉 관대화 버그"
    assert "undeclared_var" in msg, f"에러 메시지에 변수명 없음: {msg}"


def test_undeclared_variable_in_dict_formula_fails():
    """dict formula에서 미선언 변수도 여전히 FAIL이어야 한다."""
    formula_dict = {"result": "a * ghost_variable + b"}
    ok, msg = validate_formula(formula_dict, {"a": "number", "b": "number"})
    assert not ok, "dict formula 미선언 변수가 PASS됨"
    assert "ghost_variable" in msg, f"에러 메시지에 변수명 없음: {msg}"


def test_annual_leave_remaining_formula_full_validation():
    """연차잔여일계산기 formula dict 전체 검증 — HOLD-3 수정 후 정상 통과해야 한다."""
    formula_dict = {
        "total_days": "15 + min(max(0, (years_of_service - 1) // 2), 10)",
        "remaining_days": "15 + min(max(0, (years_of_service - 1) // 2), 10) - used_days",
    }
    schema = {"years_of_service": "number", "used_days": "number"}
    ok, msg = validate_formula(formula_dict, schema)
    assert ok, f"연차잔여일 formula 검증 실패: {msg}"


# ── CA-2-4: Contract Instance 영속화 테스트 ──────────────────────────────────

import yaml as _yaml_mod
from modules.app_factory import _save_contract_instance, _delete_contract_instance

_SAMPLE_CONTRACT = {
    "slug": "test-calc",
    "name": "테스트 계산기",
    "category": "노무/급여",
    "tier": "Tier2-A",
    "input_fields": ["base_pay"],
    "output_fields": ["net_pay"],
    "formula": "net_pay = base_pay * 0.9",
    "formula_status": "operator_confirmed",
    "scope_exclusions": [],
    "test_cases": [{"input": {"base_pay": 1000}, "expected": {"net_pay": 900}}],
    "test_cases_status": "operator_confirmed",
    "desc": "테스트용 계산기",
    "legal_refs": ["labor_standards_act_55"],
}


def test_mode_b_contract_instance_created(tmp_path, monkeypatch):
    """Mode B: Contract Instance 파일이 instances/{slug}.yaml에 생성된다."""
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    _save_contract_instance("test-calc", _SAMPLE_CONTRACT.copy())
    assert (tmp_path / "schema" / "instances" / "test-calc.yaml").exists()


def test_contract_instance_preserves_formula_and_test_cases(tmp_path, monkeypatch):
    """Contract Instance에 formula와 test_cases 원본이 보존된다."""
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    _save_contract_instance("test-calc", _SAMPLE_CONTRACT.copy())
    loaded = _yaml_mod.safe_load(
        (tmp_path / "schema" / "instances" / "test-calc.yaml").read_text(encoding="utf-8")
    )
    assert loaded["formula"] == "net_pay = base_pay * 0.9"
    assert loaded["test_cases"] == [{"input": {"base_pay": 1000}, "expected": {"net_pay": 900}}]


def test_contract_instance_preserves_all_fields(tmp_path, monkeypatch):
    """Contract Instance에 모든 핵심 필드가 보존된다(legal_refs/input/output/desc 포함)."""
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    _save_contract_instance("test-calc", _SAMPLE_CONTRACT.copy())
    loaded = _yaml_mod.safe_load(
        (tmp_path / "schema" / "instances" / "test-calc.yaml").read_text(encoding="utf-8")
    )
    required = ("slug", "name", "category", "tier", "input_fields", "output_fields",
                 "formula", "formula_status", "scope_exclusions", "test_cases",
                 "test_cases_status", "desc", "legal_refs", "generated_at")
    for field in required:
        assert field in loaded, f"필드 '{field}'가 Contract Instance에 없음"
    assert loaded["legal_refs"] == ["labor_standards_act_55"]
    assert loaded["input_fields"] == ["base_pay"]
    assert loaded["output_fields"] == ["net_pay"]
    assert loaded["desc"] == "테스트용 계산기"


def test_mode_a_none_contract_no_instance(tmp_path, monkeypatch):
    """Mode A (contract=None): Contract Instance 파일이 생성되지 않는다."""
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    _save_contract_instance("test-calc", None)
    assert not (tmp_path / "schema" / "instances" / "test-calc.yaml").exists()


def test_mode_a_empty_contract_no_instance(tmp_path, monkeypatch):
    """Mode A (contract={}): Contract Instance 파일이 생성되지 않는다."""
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    _save_contract_instance("test-calc", {})
    assert not (tmp_path / "schema" / "instances" / "test-calc.yaml").exists()


def test_contract_registry_updated_on_save(tmp_path, monkeypatch):
    """Contract Instance 저장 시 registry.yaml 인덱스가 갱신된다."""
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    _save_contract_instance("test-calc", _SAMPLE_CONTRACT.copy())
    reg = _yaml_mod.safe_load(
        (tmp_path / "schema" / "registry.yaml").read_text(encoding="utf-8")
    )
    assert "test-calc" in reg["instances"]
    entry = reg["instances"]["test-calc"]
    assert entry["formula_status"] == "operator_confirmed"
    assert entry["test_cases_status"] == "operator_confirmed"
    assert entry["contract_slug"] == "test-calc"
    assert "generated_at" in entry


def test_delete_contract_instance_removes_file_and_registry(tmp_path, monkeypatch):
    """delete_contract_instance(): 파일과 registry.yaml 항목이 모두 제거된다."""
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    _save_contract_instance("test-calc", _SAMPLE_CONTRACT.copy())
    assert (tmp_path / "schema" / "instances" / "test-calc.yaml").exists()
    result = _delete_contract_instance("test-calc")
    assert result is True
    assert not (tmp_path / "schema" / "instances" / "test-calc.yaml").exists()
    reg = _yaml_mod.safe_load(
        (tmp_path / "schema" / "registry.yaml").read_text(encoding="utf-8")
    )
    assert "test-calc" not in (reg.get("instances") or {})


def test_delete_contract_instance_missing_file_returns_false(tmp_path, monkeypatch):
    """Contract Instance가 없어도 _delete_contract_instance()가 오류 없이 False를 반환한다."""
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    result = _delete_contract_instance("nonexistent-calc")
    assert result is False


def test_registry_loader_ignores_contract_schema():
    """load_registry_v3()가 docs/contract_schema/를 읽지 않는다 — glob 안전성 확인."""
    from modules.registry_loader import load_registry_v3
    reg = load_registry_v3()
    # registry.yaml 최상위 키는 'instances' — 계산기 slug와 혼동될 수 없음
    assert "instances" not in reg, \
        "contract_schema/registry.yaml이 v3 Registry에 오염됨 — glob 경로 확인 필요"


# ── CA-2-6-1: formula_status 상태 머신 테스트 ────────────────────────────────

from modules.app_factory import build_contract as _build_contract


def test_formula_status_not_generated_when_no_formula():
    """formula=None → formula_status='not_generated'."""
    c = _build_contract("x", "X")
    assert c["formula_status"] == "not_generated"


def test_formula_status_pending_validation_when_formula_given():
    """formula 제공 + formula_status 미지정 → 'pending_validation' (CA-2-6-1 핵심 변경)."""
    c = _build_contract("x", "X", formula="a + b")
    assert c["formula_status"] == "pending_validation"


def test_formula_status_explicit_operator_confirmed_preserved():
    """formula_status='operator_confirmed' 명시 → 그대로 보존."""
    c = _build_contract("x", "X", formula="a + b", formula_status="operator_confirmed")
    assert c["formula_status"] == "operator_confirmed"


def test_formula_status_explicit_pending_validation_preserved():
    """formula_status='pending_validation' 명시 → 그대로 보존."""
    c = _build_contract("x", "X", formula="a + b", formula_status="pending_validation")
    assert c["formula_status"] == "pending_validation"


def test_contract_instance_stores_pending_validation_status(tmp_path, monkeypatch):
    """pending_validation 상태의 Contract Instance가 저장되고 복구된다."""
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    contract = _build_contract("pv-calc", "PV Test", formula="a * b")
    assert contract["formula_status"] == "pending_validation"
    _save_contract_instance("pv-calc", contract)
    loaded = _yaml_mod.safe_load(
        (tmp_path / "schema" / "instances" / "pv-calc.yaml").read_text(encoding="utf-8")
    )
    assert loaded["formula_status"] == "pending_validation"


# ── CA-2-6-2: Contract Formula 검증 UI 연결 테스트 ───────────────────────────

from modules.formula_engine import validate_formula_with_samples as _vfws


def test_input_fields_to_schema_conversion():
    """input_fields list → input_schema dict 변환 (Dashboard 검증 버튼 로직)."""
    contract = _build_contract("x", "X", input_fields=["years_of_service", "used_days"])
    schema = {f: "number" for f in contract["input_fields"]}
    assert schema == {"years_of_service": "number", "used_days": "number"}


def test_validation_pass_then_operator_confirmed():
    """TEST-2: 검증 통과 후 operator_confirmed 설정 흐름."""
    contract = _build_contract(
        "x", "X",
        formula="a * 2",
        input_fields=["a"],
        test_cases=[{"input": {"a": 5}, "expected": {"result": 10.0}}],
    )
    assert contract["formula_status"] == "pending_validation"
    schema = {f: "number" for f in contract["input_fields"]}
    result = _vfws(contract["formula"], schema, contract["test_cases"])
    # 검증 통과 판정 (_fv_passed 로직 재현)
    fv_passed = result.get("valid", False) and not any(
        s.get("match") is False for s in result.get("sample_results", [])
    )
    assert fv_passed, f"검증 실패: {result['message']}"
    # [Formula 확정] 버튼 클릭 시 dashboard가 수행하는 동작
    contract["formula_status"] = "operator_confirmed"
    assert contract["formula_status"] == "operator_confirmed"


def test_formula_modification_resets_to_pending_validation():
    """TEST-3: 확정된 Formula를 수정하면 pending_validation으로 복귀."""
    contract = _build_contract("x", "X", formula="a + b", formula_status="operator_confirmed")
    assert contract["formula_status"] == "operator_confirmed"
    confirmed_raw = "a + b"   # 확정 시점의 raw 텍스트 (af_formula_confirmed_text)
    new_raw = "a * b"          # 운영자가 수정한 새 텍스트
    # Dashboard 수정 감지 로직 재현
    if new_raw != confirmed_raw:
        contract["formula_status"] = "pending_validation"
    assert contract["formula_status"] == "pending_validation"


def test_validation_fail_prevents_confirmation():
    """TEST-4: 검증 실패 시 _fv_passed=False → 확정 버튼 비활성 판정."""
    result = _vfws("a + ghost_var", {"a": "number"})
    assert not result["valid"]
    fv_passed = result.get("valid", False) and not any(
        s.get("match") is False for s in result.get("sample_results", [])
    )
    assert not fv_passed, "검증 실패인데 확정 허용 판정이 True"


# ── CA-3-1: ai_suggested 상태 Lifecycle 테스트 ────────────────────────────────

from modules.app_factory import check_hold_rules as _check_hold_rules


def test_formula_status_ai_suggested_preserved():
    """CA-3-1 TEST-3: formula_status='ai_suggested' 명시 → 그대로 보존."""
    c = _build_contract("x", "X", formula="a * 2", formula_status="ai_suggested")
    assert c["formula_status"] == "ai_suggested"


def test_hold1_fires_for_ai_suggested():
    """CA-3-1 TEST-4: ai_suggested → check_hold_rules() → HOLD-1 발생."""
    contract = _build_contract(
        "x", "X",
        formula="a * 2",
        input_fields=["a"],
        formula_status="ai_suggested",
        category="기타",
    )
    result = _check_hold_rules(contract)
    assert result["held"] is True
    assert "HOLD-1" in result["rules"]


def test_hold1_not_fires_for_operator_confirmed():
    """CA-3-1 TEST-5: operator_confirmed → check_hold_rules() → HOLD-1 미발생."""
    contract = _build_contract(
        "x", "X",
        formula="a * 2",
        input_fields=["a"],
        formula_status="operator_confirmed",
        category="기타",
    )
    result = _check_hold_rules(contract)
    assert "HOLD-1" not in result["rules"]


def test_contract_instance_stores_ai_suggested_status(tmp_path, monkeypatch):
    """CA-3-1 TEST-6: ai_suggested 상태의 Contract Instance 저장/로드."""
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    contract = _build_contract(
        "ai-calc", "AI Test",
        formula="a * b",
        formula_status="ai_suggested",
        input_fields=["a", "b"],
        output_fields=["result"],
    )
    assert contract["formula_status"] == "ai_suggested"
    _save_contract_instance("ai-calc", contract)
    loaded = _yaml_mod.safe_load(
        (tmp_path / "schema" / "instances" / "ai-calc.yaml").read_text(encoding="utf-8")
    )
    assert loaded["formula_status"] == "ai_suggested"


def test_ai_suggested_modification_resets_to_pending_validation():
    """CA-3-1 TEST-7: ai_suggested 상태에서 Formula 수정 시 pending_validation으로 복귀."""
    contract = _build_contract("x", "X", formula="a + b", formula_status="ai_suggested")
    assert contract["formula_status"] == "ai_suggested"
    ai_suggested_raw = "a + b"
    new_raw = "a * b"
    # Dashboard CA-3-1 수정 감지 로직 재현
    if ai_suggested_raw and new_raw != ai_suggested_raw:
        contract["formula_status"] = "pending_validation"
    assert contract["formula_status"] == "pending_validation"


def test_ai_suggested_no_change_stays_ai_suggested():
    """CA-3-1: ai_suggested 상태에서 Formula 미수정 시 상태 유지."""
    contract = _build_contract("x", "X", formula="a + b", formula_status="ai_suggested")
    ai_suggested_raw = "a + b"
    current_raw = "a + b"
    if ai_suggested_raw and current_raw != ai_suggested_raw:
        contract["formula_status"] = "pending_validation"
    assert contract["formula_status"] == "ai_suggested"


def test_ai_suggested_not_equal_operator_confirmed():
    """CA-3-1 원칙 1: ai_suggested ≠ operator_confirmed — 직접 동치 불가."""
    assert "ai_suggested" != "operator_confirmed"
    contract = _build_contract("x", "X", formula="a * 2", formula_status="ai_suggested")
    assert contract["formula_status"] != "operator_confirmed"


# ── CA-3-4: Dashboard AI Formula 제안 버튼 연결 테스트 ────────────────────────

import json as _json_mod
from modules.app_factory import AF_SESSION_DISCARD_KEYS


def test_ca34_empty_formula_ai_suggest_succeeds():
    """TEST-1: 빈 Formula → AI 제안 성공 → ai_suggested 상태."""
    contract = _build_contract("x", "X", input_fields=["a"], output_fields=["b"])
    # AI 제안 성공 시 Dashboard가 수행하는 세션 업데이트 로직 재현
    _sf_formula_str = "a * 2"
    session = {}
    session["af_contract_formula"] = _sf_formula_str
    session["af_formula_ai_suggested_text"] = _sf_formula_str
    session.pop("af_formula_confirmed_text", None)
    session.pop("af_formula_validation", None)
    contract["formula_status"] = "ai_suggested"
    assert contract["formula_status"] == "ai_suggested"
    assert session.get("af_formula_ai_suggested_text") == _sf_formula_str
    assert "af_formula_confirmed_text" not in session


def test_ca34_existing_formula_first_click_no_overwrite():
    """TEST-2: 기존 Formula 존재 → 1차 클릭에서 덮어쓰기 안 됨."""
    existing = "a + b"
    session = {"af_contract_formula": existing}
    override_flag = session.pop("_af_ai_suggest_override", False)
    # 1차 클릭 흐름 재현: 기존 formula 있고 override 없음 → 경고 후 플래그 설정
    if existing and not override_flag:
        session["_af_ai_suggest_override"] = True
        performed_overwrite = False
    else:
        performed_overwrite = True
    assert not performed_overwrite
    assert session.get("_af_ai_suggest_override") is True
    # formula는 변경되지 않아야 함
    assert session["af_contract_formula"] == existing


def test_ca34_second_click_applies_ai_formula():
    """TEST-3: 2차 확인 → AI Formula 교체 → ai_suggested."""
    existing = "a + b"
    session = {
        "af_contract_formula": existing,
        "_af_ai_suggest_override": True,  # 1차 클릭에서 설정된 플래그
    }
    # 2차 클릭 흐름 재현
    override_flag = session.pop("_af_ai_suggest_override", False)
    if existing and not override_flag:
        session["_af_ai_suggest_override"] = True
        performed_overwrite = False
    else:
        # AI 호출 성공 시 수행 로직
        _new_formula = "a * 3"
        session["af_contract_formula"] = _new_formula
        session["af_formula_ai_suggested_text"] = _new_formula
        session.pop("af_formula_confirmed_text", None)
        session.pop("af_formula_validation", None)
        performed_overwrite = True
    assert performed_overwrite
    assert session["af_contract_formula"] == "a * 3"
    assert session.get("af_formula_ai_suggested_text") == "a * 3"
    assert "_af_ai_suggest_override" not in session


def test_ca34_ai_failure_keeps_existing_formula():
    """TEST-4: AI 호출 실패 → 기존 Formula 유지, 기존 status 유지."""
    existing = "a + b"
    session = {
        "af_contract_formula": existing,
        "af_formula_ai_suggested_text": "",
    }
    contract = _build_contract("x", "X", formula=existing, formula_status="pending_validation")
    # 실패 시 session state 변경 없음 (Dashboard 로직: st.error()만 표시)
    _sf_result = {"success": False, "reason": "AI 호출 실패", "warnings": []}
    if _sf_result["success"]:
        session["af_contract_formula"] = _sf_result.get("formula", "")
        contract["formula_status"] = "ai_suggested"
    # 아무 것도 변경되지 않아야 함
    assert session["af_contract_formula"] == existing
    assert contract["formula_status"] == "pending_validation"


def test_ca34_ai_suggest_then_modify_resets_to_pending():
    """TEST-5: AI 제안 → Formula 수정 → pending_validation."""
    ai_formula = "a * 2"
    session = {"af_formula_ai_suggested_text": ai_formula}
    contract = _build_contract("x", "X", formula=ai_formula, formula_status="ai_suggested")
    # 운영자가 formula 수정 (CA-3-1 수정 감지 로직 재현)
    new_raw = "a * 3"
    ai_raw = session.get("af_formula_ai_suggested_text", "")
    if ai_raw and new_raw != ai_raw:
        session.pop("af_formula_ai_suggested_text", None)
        session.pop("af_formula_validation", None)
        contract["formula_status"] = "pending_validation"
    assert contract["formula_status"] == "pending_validation"
    assert "af_formula_ai_suggested_text" not in session


def test_ca34_dict_formula_serialization_round_trip():
    """TEST-6: dict Formula → compact JSON 직렬화 → json.loads() 복원."""
    dict_formula = {
        "national_pension": "monthly_salary * 0.045",
        "health_insurance": "monthly_salary * 0.03545",
    }
    # Dashboard: dict → compact JSON → text_area 저장
    stored_str = _json_mod.dumps(dict_formula, ensure_ascii=False)
    # build_contract() 블록: json.loads() 복원
    restored = _json_mod.loads(stored_str)
    assert isinstance(restored, dict)
    assert restored == dict_formula
    # ai_suggested_text와 비교 시 동일해야 함 (whitespace 일관성)
    assert stored_str == _json_mod.dumps(dict_formula, ensure_ascii=False)


def test_ca34_discard_keys_include_ai_formula_keys():
    """TEST-7: AF_SESSION_DISCARD_KEYS에 AI Formula 관련 4개 키가 포함된다."""
    required_keys = {
        "af_formula_confirmed_text",
        "af_formula_validation",
        "af_formula_ai_suggested_text",
        "_af_ai_suggest_override",
    }
    assert required_keys.issubset(set(AF_SESSION_DISCARD_KEYS)), (
        f"AF_SESSION_DISCARD_KEYS에 누락된 키: {required_keys - set(AF_SESSION_DISCARD_KEYS)}"
    )
