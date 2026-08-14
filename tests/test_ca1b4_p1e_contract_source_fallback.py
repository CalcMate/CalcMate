# -*- coding: utf-8 -*-
"""tests/test_ca1b4_p1e_contract_source_fallback.py — CA-1B-4 P1-E

Contract Instance 파일이 없는 경우, Registry에 저장된 contract_source 최소
snapshot으로 안전한 부분 복원(프리필 지원)을 수행하는 fallback 검증.

검증 항목 (모두 tmp_path + monkeypatch, 실제 docs/registry/·legal_master·instances/ 무접촉):
  1.  instance 없음 + Registry contract_source 존재 → found=True, input/output 복원
  2.  Registry legal_refs 연결
  3.  scope_exclusions 연동 (legal_master forbidden 경로 재사용)
  4.  formula/test_cases snapshot 상태 존재해도 실제 formula/test_cases 생성 안 함
  5.  instance 없음 + contract_source=None → 기존 found=False + 메시지 유지
  6.  Registry에 slug 없음 → 기존 found=False 유지
  7.  instance 파일 존재 → instance 우선 (Registry fallback 미발동)
  8.  Mode A (contract_source=None) → fallback 미발동
  9.  slug path traversal → 기존 보안 동작 유지
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from modules.app_factory import _save_contract_instance, contract_instance_restore


def _fake_contract_source_entry(contract_source=None, legal_refs=None, name="스냅샷 계산기"):
    """Registry entry 모사 — Mode B(contract_source dict) 또는 Mode A(None/키 없음)."""
    entry = {
        "name": name,
        "slug": "snapshot-calc",
        "category": "노무/급여",
        "legal_refs": list(legal_refs or []),
        "contract_source": contract_source,
    }
    return entry


def _mk_contract_source(**overrides):
    cs = {
        "contract_slug": "snapshot-calc",
        "input_fields": ["base_pay", "extra_pay"],
        "output_fields": ["total_pay"],
        "formula_status": "operator_confirmed",
        "test_cases_status": "not_generated",
    }
    cs.update(overrides)
    return cs


def _patch_schema_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")


# ── 1. instance 없음 + contract_source 존재 → 부분 복원 ────────────────────
def test_fallback_restores_input_output_when_instance_missing(tmp_path, monkeypatch):
    _patch_schema_dir(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "modules.registry_loader.load_registry_v3",
        lambda: {"snapshot-calc": _fake_contract_source_entry(_mk_contract_source())},
    )
    rest = contract_instance_restore("snapshot-calc")
    assert rest["found"] is True
    assert rest["slug"] == "snapshot-calc"
    assert rest["name"] == "스냅샷 계산기"
    assert rest["input_fields"] == ["base_pay", "extra_pay"]
    assert rest["output_fields"] == ["total_pay"]
    assert "부분 복원" in rest["message"]
    assert "snapshot" in rest["message"]


# ── 2. Registry legal_refs 연결 ────────────────────────────────────────────
def test_fallback_links_registry_legal_refs(tmp_path, monkeypatch):
    _patch_schema_dir(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "modules.registry_loader.load_registry_v3",
        lambda: {"snapshot-calc": _fake_contract_source_entry(
            _mk_contract_source(), legal_refs=["labor_standards_act_55"])},
    )
    rest = contract_instance_restore("snapshot-calc")
    assert rest["found"] is True
    assert rest["legal_refs"] == ["labor_standards_act_55"]


# ── 3. scope_exclusions 연동 (legal_master 경로 재사용) ────────────────────
def test_fallback_scope_exclusions_via_legal_master(tmp_path, monkeypatch):
    _patch_schema_dir(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "modules.registry_loader.load_registry_v3",
        lambda: {"snapshot-calc": _fake_contract_source_entry(
            _mk_contract_source(), legal_refs=["labor_standards_act_55"])},
    )
    monkeypatch.setattr(
        "modules.registry_loader.load_legal_master",
        lambda: {"labor_standards_act_55": {
            "forbidden_articles": ["근로기준법 제34조"],
            "forbidden_phrases": ["최저임금 미만"],
        }},
    )
    rest = contract_instance_restore("snapshot-calc")
    assert rest["found"] is True
    assert rest["scope_exclusions"] == ["근로기준법 제34조", "최저임금 미만"]


# ── 4. snapshot 상태여도 formula/test_cases 생성 안 함 ─────────────────────
def test_fallback_never_invents_formula_or_test_cases(tmp_path, monkeypatch):
    _patch_schema_dir(tmp_path, monkeypatch)
    # formula_status=operator_confirmed 이더라도 실제 formula는 snapshot에 없음
    monkeypatch.setattr(
        "modules.registry_loader.load_registry_v3",
        lambda: {"snapshot-calc": _fake_contract_source_entry(_mk_contract_source())},
    )
    rest = contract_instance_restore("snapshot-calc")
    assert rest["found"] is True
    assert rest["formula"] is None
    assert rest["test_cases"] == []
    assert rest["formula_status"] == "operator_confirmed"
    assert rest["test_cases_status"] == "not_generated"


# ── 5. contract_source=None → 기존 found=False + 메시지 유지 ───────────────
def test_fallback_skipped_when_contract_source_none(tmp_path, monkeypatch):
    _patch_schema_dir(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "modules.registry_loader.load_registry_v3",
        lambda: {"snapshot-calc": _fake_contract_source_entry(None)},
    )
    rest = contract_instance_restore("snapshot-calc")
    assert rest["found"] is False
    assert rest["instance"] is None
    assert rest["input_fields"] == []
    assert "Contract instance가 없습니다" in rest["message"]


# ── 6. Registry에 slug 없음 → 기존 found=False 유지 ────────────────────────
def test_fallback_skipped_when_slug_not_in_registry(tmp_path, monkeypatch):
    _patch_schema_dir(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "modules.registry_loader.load_registry_v3",
        lambda: {"other-calc": _fake_contract_source_entry(_mk_contract_source())},
    )
    rest = contract_instance_restore("no-such-calc")
    assert rest["found"] is False
    assert rest["message"] == "Contract instance가 없습니다: 'no-such-calc'"


# ── 7. instance 파일 존재 → instance 우선 (fallback 미발동) ────────────────
def test_instance_file_takes_priority(tmp_path, monkeypatch):
    _patch_schema_dir(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "modules.registry_loader.load_registry_v3",
        lambda: {"snapshot-calc": _fake_contract_source_entry(_mk_contract_source(
            input_fields=["snap_in"], output_fields=["snap_out"]))},
    )
    _save_contract_instance("snapshot-calc", {
        "slug": "snapshot-calc",
        "name": "실제 instance",
        "category": "노무/급여",
        "tier": "Tier2-A",
        "input_fields": ["base_pay"],
        "output_fields": ["net_pay"],
        "formula": "base_pay * 0.9",
        "formula_status": "pending_validation",
        "scope_exclusions": [],
        "test_cases": [],
        "test_cases_status": "not_generated",
        "desc": "",
        "legal_refs": [],
    })
    rest = contract_instance_restore("snapshot-calc")
    assert rest["found"] is True
    # instance 파일 우선 — Registry snapshot 값이 아님
    assert rest["input_fields"] == ["base_pay"]
    assert rest["output_fields"] == ["net_pay"]
    assert rest["formula"] == "base_pay * 0.9"
    assert rest["message"] == ""
    assert rest["instance"] is not None


# ── 8. Mode A (contract_source 키 자체 없음) → fallback 미발동 ─────────────
def test_fallback_skipped_for_mode_a_entry(tmp_path, monkeypatch):
    _patch_schema_dir(tmp_path, monkeypatch)
    entry = _fake_contract_source_entry()
    entry.pop("contract_source", None)  # Mode A — 키 자체가 없음
    monkeypatch.setattr(
        "modules.registry_loader.load_registry_v3",
        lambda: {"snapshot-calc": entry},
    )
    rest = contract_instance_restore("snapshot-calc")
    assert rest["found"] is False
    assert rest["input_fields"] == []
    assert "Contract instance가 없습니다" in rest["message"]


# ── 9. slug path traversal → 기존 보안 동작 유지 ───────────────────────────
def test_fallback_traversal_slug_safe(tmp_path, monkeypatch):
    _patch_schema_dir(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "modules.registry_loader.load_registry_v3",
        lambda: {"snapshot-calc": _fake_contract_source_entry(_mk_contract_source())},
    )
    rest = contract_instance_restore("../../etc/passwd")
    assert rest["found"] is False
    assert rest["instance"] is None
    assert rest["message"]
