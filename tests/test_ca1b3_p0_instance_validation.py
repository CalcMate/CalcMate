# -*- coding: utf-8 -*-
"""tests/test_ca1b3_p0_instance_validation.py — CA-1B-3-B P0: Contract Instance Schema Validation

검증 항목 (모두 tmp_path 사용, 실제 docs/contract_schema/instances/에는 쓰지 않음):
  1.  정상 Contract instance → PASS
  2.  slug 누락 → ValueError
  3.  name 누락 → ValueError
  4.  formula_status 잘못된 값 → ValueError
  5.  test_cases_status 잘못된 값 → ValueError
  6.  input_fields가 list 아님 → ValueError
  7.  output_fields가 list 아님 → ValueError
  8.  scope_exclusions가 list 아님 → ValueError
  9.  legal_refs가 list 아님 → ValueError
 10.  generated_at이 잘못된 날짜 형식 → ValueError
 11.  formula가 허용 타입 아님 → ValueError
 12.  기존 malformed YAML 처리 유지
 13.  slug path traversal 방어 유지
 14.  정상 save → load 왕복 → PASS
"""
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from modules.app_factory import (
    _save_contract_instance,
    load_contract_instance,
    validate_contract_instance,
)

_VALID_INSTANCE = {
    "slug": "test-calc",
    "name": "테스트 계산기",
    "category": "노무/급여",
    "tier": "Tier2-A",
    "input_fields": ["base_pay"],
    "output_fields": ["net_pay"],
    "formula": "base_pay * 0.9",
    "formula_status": "operator_confirmed",
    "scope_exclusions": [],
    "test_cases": [],
    "test_cases_status": "operator_confirmed",
    "desc": "테스트용 계산기",
    "legal_refs": ["labor_standards_act_55"],
    "generated_at": "2026-08-14T12:00:00+09:00",
}


def _write_instance(tmp_path, instance: dict, slug: str = "test-calc") -> Path:
    inst_dir = tmp_path / "schema" / "instances"
    inst_dir.mkdir(parents=True, exist_ok=True)
    path = inst_dir / f"{slug}.yaml"
    path.write_text(yaml.safe_dump(instance, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


# ── A. validate_contract_instance 직접 (오류 메시지 확인) ───────────────────


def test_validate_valid_instance_returns_empty():
    assert validate_contract_instance(dict(_VALID_INSTANCE)) == []


def test_validate_non_dict_returns_error():
    errors = validate_contract_instance([1, 2])
    assert errors and "dict" in errors[0]
    assert validate_contract_instance({})  # 빈 dict도 오류


def test_validate_slug_missing_message():
    inst = dict(_VALID_INSTANCE)
    inst.pop("slug")
    assert any("slug" in e for e in validate_contract_instance(inst))


def test_validate_name_missing_message():
    inst = dict(_VALID_INSTANCE)
    inst["name"] = "   "
    assert any("name" in e for e in validate_contract_instance(inst))


def test_validate_formula_status_bad_message():
    inst = dict(_VALID_INSTANCE)
    inst["formula_status"] = "auto_disabled"
    assert any("formula_status" in e for e in validate_contract_instance(inst))


def test_validate_test_cases_status_bad_message():
    inst = dict(_VALID_INSTANCE)
    inst["test_cases_status"] = "pending_validation"
    assert any("test_cases_status" in e for e in validate_contract_instance(inst))


def test_validate_list_fields_bad_message():
    for field in ("input_fields", "output_fields", "scope_exclusions", "legal_refs"):
        inst = dict(_VALID_INSTANCE)
        inst[field] = "not-a-list"
        assert any(field in e for e in validate_contract_instance(inst)), field


def test_validate_generated_at_bad_message():
    inst = dict(_VALID_INSTANCE)
    inst["generated_at"] = "2026-13-99 99:99:99"
    assert any("generated_at" in e for e in validate_contract_instance(inst))


def test_validate_formula_bad_type_message():
    inst = dict(_VALID_INSTANCE)
    inst["formula"] = 12345
    assert any("formula" in e for e in validate_contract_instance(inst))


def test_validate_formula_optional():
    inst = dict(_VALID_INSTANCE)
    inst.pop("formula")
    assert validate_contract_instance(inst) == []
    inst2 = dict(_VALID_INSTANCE)
    inst2["formula"] = None
    assert validate_contract_instance(inst2) == []


# ── B. load_contract_instance 경유 (ValueError + 필드명 메시지) ──────────────


def _assert_load_raises(tmp_path, monkeypatch, mutate, match_field):
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    inst = dict(_VALID_INSTANCE)
    mutate(inst)
    _write_instance(tmp_path, inst)
    with pytest.raises(ValueError, match=match_field):
        load_contract_instance("test-calc")


def test_load_valid_instance_passes(tmp_path, monkeypatch):
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    _write_instance(tmp_path, _VALID_INSTANCE)
    loaded = load_contract_instance("test-calc")
    assert loaded["slug"] == "test-calc"
    assert loaded["formula_status"] == "operator_confirmed"


def test_load_slug_missing_raises(tmp_path, monkeypatch):
    _assert_load_raises(tmp_path, monkeypatch, lambda i: i.pop("slug"), "slug")


def test_load_name_missing_raises(tmp_path, monkeypatch):
    _assert_load_raises(tmp_path, monkeypatch, lambda i: i.pop("name"), "name")


def test_load_formula_status_bad_raises(tmp_path, monkeypatch):
    _assert_load_raises(
        tmp_path, monkeypatch, lambda i: i.__setitem__("formula_status", "auto_disabled"), "formula_status"
    )


def test_load_test_cases_status_bad_raises(tmp_path, monkeypatch):
    _assert_load_raises(
        tmp_path, monkeypatch, lambda i: i.__setitem__("test_cases_status", "pending_validation"), "test_cases_status"
    )


@pytest.mark.parametrize("field", ["input_fields", "output_fields", "scope_exclusions", "legal_refs"])
def test_load_list_field_not_list_raises(tmp_path, monkeypatch, field):
    _assert_load_raises(
        tmp_path, monkeypatch, lambda i: i.__setitem__(field, "not-a-list"), field
    )


def test_load_generated_at_bad_raises(tmp_path, monkeypatch):
    _assert_load_raises(
        tmp_path, monkeypatch, lambda i: i.__setitem__("generated_at", "not-a-date"), "generated_at"
    )


def test_load_formula_bad_type_raises(tmp_path, monkeypatch):
    _assert_load_raises(tmp_path, monkeypatch, lambda i: i.__setitem__("formula", [1, 2]), "formula")


# ── C. 기존 동작 유지 ────────────────────────────────────────────────────────


def test_load_malformed_yaml_still_raises(tmp_path, monkeypatch):
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    inst_dir = tmp_path / "schema" / "instances"
    inst_dir.mkdir(parents=True)
    (inst_dir / "bad.yaml").write_text("{{{{ not yaml", encoding="utf-8")
    with pytest.raises(ValueError, match="파싱 실패"):
        load_contract_instance("bad")


@pytest.mark.parametrize("bad_slug", ["../etc/passwd", "a/b", "a\\b", "..", "a..b", ""])
def test_load_path_traversal_still_raises(bad_slug, tmp_path, monkeypatch):
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    with pytest.raises(ValueError):
        load_contract_instance(bad_slug)


# ── D. save → load 왕복 ──────────────────────────────────────────────────────


def test_save_load_roundtrip_passes(tmp_path, monkeypatch):
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    _save_contract_instance("test-calc", dict(_VALID_INSTANCE))
    loaded = load_contract_instance("test-calc")
    assert loaded is not None
    for key in ("slug", "name", "input_fields", "output_fields", "formula",
                "formula_status", "test_cases_status", "scope_exclusions",
                "test_cases", "legal_refs", "desc"):
        assert loaded[key] == _VALID_INSTANCE[key], key
    assert "generated_at" in loaded
