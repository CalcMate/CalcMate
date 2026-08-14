# -*- coding: utf-8 -*-
"""tests/test_ca1b4_instance_restore.py — CA-1B-4 P0: Contract Instance 복원 경로

Dashboard [📂 Contract Instance 불러오기]가 사용하는 contract_instance_restore() 검증.
저장(save→load) → 복원(restore) 왕복이 실제로 닫히는지 확인.

검증 항목 (모두 tmp_path + monkeypatch, 실제 docs/contract_schema/instances/에는 쓰지 않음):
  1.  save → restore 왕복 (str formula) — 필드 전체 복원
  2.  dict formula 왕복
  3.  operator_confirmed 상태 보존 + scope_exclusions/test_cases 복원
  4.  instance 없음 → found=False + message
  5.  malformed YAML → found=False + message (예외 전파 없음)
  6.  instance가 dict 아님 → found=False + message
  7.  slug path traversal → found=False + message
  8.  registry 인덱스(load_contract_registry) 연동 확인
"""
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from modules.app_factory import (
    _save_contract_instance,
    contract_instance_restore,
    load_contract_registry,
)


def _mk_contract(formula="base_pay * 0.9",
                 formula_status="operator_confirmed",
                 test_cases=None,
                 scope_exclusions=None,
                 legal_refs=None):
    return {
        "slug": "test-calc",
        "name": "테스트 계산기",
        "category": "노무/급여",
        "tier": "Tier2-A",
        "input_fields": ["base_pay"],
        "output_fields": ["net_pay"],
        "formula": formula,
        "formula_status": formula_status,
        "scope_exclusions": list(scope_exclusions or []),
        "test_cases": list(test_cases or []),
        "test_cases_status": "operator_confirmed" if test_cases else "not_generated",
        "desc": "테스트용 계산기",
        "legal_refs": list(legal_refs or []),
    }


# ── 1. save → restore 왕복 (str formula) ───────────────────────────────────
def test_restore_roundtrip_str_formula(tmp_path, monkeypatch):
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    _save_contract_instance("test-calc", _mk_contract())
    rest = contract_instance_restore("test-calc")
    assert rest["found"] is True
    assert rest["slug"] == "test-calc"
    assert rest["name"] == "테스트 계산기"
    assert rest["input_fields"] == ["base_pay"]
    assert rest["output_fields"] == ["net_pay"]
    assert rest["formula"] == "base_pay * 0.9"
    assert rest["formula_status"] == "operator_confirmed"
    assert rest["message"] == ""


# ── 2. dict formula 왕복 ───────────────────────────────────────────────────
def test_restore_roundtrip_dict_formula(tmp_path, monkeypatch):
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    f = {"net_pay": "base_pay * 0.9", "gross": "base_pay * 1.1"}
    _save_contract_instance("test-calc", _mk_contract(formula=f))
    rest = contract_instance_restore("test-calc")
    assert rest["found"] is True
    assert rest["formula"] == f


# ── 3. operator_confirmed 보존 + scope_exclusions/test_cases 복원 ──────────
def test_restore_preserves_status_and_aux_fields(tmp_path, monkeypatch):
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    c = _mk_contract(
        scope_exclusions=["근로기준법 제34조"],
        test_cases=[{"input": {"base_pay": 1000}, "expected": {"net_pay": 900}}],
        legal_refs=["labor_standards_act_55"],
    )
    _save_contract_instance("test-calc", c)
    rest = contract_instance_restore("test-calc")
    assert rest["found"] is True
    assert rest["formula_status"] == "operator_confirmed"
    assert rest["scope_exclusions"] == ["근로기준법 제34조"]
    assert rest["test_cases"] == [{"input": {"base_pay": 1000}, "expected": {"net_pay": 900}}]
    assert rest["instance"]["legal_refs"] == ["labor_standards_act_55"]


# ── 4. instance 없음 → found=False + message ───────────────────────────────
def test_restore_missing_instance(tmp_path, monkeypatch):
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    rest = contract_instance_restore("no-such-calc")
    assert rest["found"] is False
    assert rest["instance"] is None
    assert rest["input_fields"] == []
    assert rest["message"]


# ── 5. malformed YAML → found=False + message (예외 전파 없음) ─────────────
def test_restore_malformed_yaml(tmp_path, monkeypatch):
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    d = tmp_path / "schema" / "instances"
    d.mkdir(parents=True)
    (d / "bad-calc.yaml").write_text("slug: [unclosed\n", encoding="utf-8")
    rest = contract_instance_restore("bad-calc")
    assert rest["found"] is False
    assert "파싱 실패" in rest["message"]


# ── 6. instance가 dict 아님 → found=False + message ────────────────────────
def test_restore_non_dict_instance(tmp_path, monkeypatch):
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    d = tmp_path / "schema" / "instances"
    d.mkdir(parents=True)
    (d / "list-calc.yaml").write_text("- just\n- a\n- list\n", encoding="utf-8")
    rest = contract_instance_restore("list-calc")
    assert rest["found"] is False
    assert "구조가 올바르지 않습니다" in rest["message"]


# ── 7. slug path traversal → found=False + message ─────────────────────────
def test_restore_traversal_slug(tmp_path, monkeypatch):
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    rest = contract_instance_restore("../../etc/passwd")
    assert rest["found"] is False
    assert rest["message"]


# ── 8. registry 인덱스(load_contract_registry) 연동 확인 ──────────────────
def test_restore_after_save_registry_index(tmp_path, monkeypatch):
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    _save_contract_instance("test-calc", _mk_contract(formula_status="pending_validation"))
    idx = load_contract_registry()
    assert "test-calc" in idx
    assert idx["test-calc"]["formula_status"] == "pending_validation"
    # restore는 인덱스와 무관하게 instance 파일에서 읽는다
    rest = contract_instance_restore("test-calc")
    assert rest["found"] is True
    assert rest["formula_status"] == "pending_validation"
