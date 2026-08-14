# -*- coding: utf-8 -*-
"""tests/test_ca1b3_prefill_and_loader.py — CA-1B-3-A: Registry→Contract 프리필 + Instance Loader

검증 항목:
  A. Registry input_labels/output_labels → Contract 프리필 (8개 계산기 실데이터)
  B. prefill 결과 → build_contract() 전달 시 input_fields/output_fields 일치
  C. Loader save→load 왕복 — _save_contract_instance() 후 load_contract_instance() 동일성
  D. Loader 안전성 — 파일 없음(None) / malformed YAML(ValueError) / path traversal(ValueError)
  E. load_contract_registry() — 빈 상태/저장 후 인덱스
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from modules.app_factory import (
    _save_contract_instance,
    build_contract,
    load_contract_instance,
    load_contract_registry,
    prefill_contract_from_registry,
)

# CA-1B-1에서 검증 완료된 8개 계산기
_EIGHT_SLUGS = [
    "weekly-holiday-allowance",
    "severance-pay",
    "annual-leave-allowance",
    "연말정산_환급액_계산기",
    "freelancer-tax-3p3",
    "unemployment-benefit",
    "육아휴직_급여_계산기",
    "four-insurances",
]

_SAMPLE_CONTRACT = {
    "slug": "test-calc",
    "name": "테스트 계산기",
    "category": "노무/급여",
    "tier": "Tier2-A",
    "input_fields": ["base_pay"],
    "output_fields": ["net_pay"],
    "formula": "base_pay * 0.9",
    "formula_status": "operator_confirmed",
    "scope_exclusions": [],
    "test_cases": [{"input": {"base_pay": 1000}, "expected": {"net_pay": 900}}],
    "test_cases_status": "operator_confirmed",
    "desc": "테스트용 계산기",
    "legal_refs": ["labor_standards_act_55"],
}


# ── A. Registry → Prefill (실데이터) ────────────────────────────────────────


def test_prefill_8_calculators_match_registry():
    """8개 계산기: prefill.input_fields == Registry input_labels, output_fields == output_labels."""
    from modules.registry_loader import load_registry_v3

    reg = load_registry_v3(force=True)
    for slug in _EIGHT_SLUGS:
        entry = reg[slug]
        pf = prefill_contract_from_registry(slug)
        assert pf["found"] is True, slug
        assert pf["input_fields"] == list(entry.get("input_labels") or []), slug
        assert pf["output_fields"] == list(entry.get("output_labels") or []), slug
        assert pf["name"] == entry.get("name"), slug
        assert pf["category"] == entry.get("category"), slug


def test_prefill_to_build_contract_roundtrip():
    """prefill → build_contract(): contract.input_fields/output_fields와 정확히 일치."""
    from modules.registry_loader import load_registry_v3

    reg = load_registry_v3(force=True)
    for slug in _EIGHT_SLUGS:
        entry = reg[slug]
        pf = prefill_contract_from_registry(slug)
        contract = build_contract(
            slug=slug,
            name=pf["name"] or entry.get("name", ""),
            category=entry.get("category", ""),
            input_fields=pf["input_fields"],
            output_fields=pf["output_fields"],
        )
        assert contract["input_fields"] == list(entry.get("input_labels") or []), slug
        assert contract["output_fields"] == list(entry.get("output_labels") or []), slug


def test_prefill_missing_slug():
    """Registry에 없는 slug → found=False, 빈 리스트 (추측 없음)."""
    pf = prefill_contract_from_registry("no-such-calculator-xyz")
    assert pf["found"] is False
    assert pf["entry"] is None
    assert pf["input_fields"] == []
    assert pf["output_fields"] == []
    assert pf["message"]


def test_prefill_missing_labels_no_guess():
    """input_labels/output_labels가 없는 엔트리 → 빈 리스트 (추측 금지)."""
    reg = {"bare": {"slug": "bare", "name": "bare", "category": ""}}
    pf = prefill_contract_from_registry("bare", registry=reg)
    assert pf["found"] is True
    assert pf["input_fields"] == []
    assert pf["output_fields"] == []


def test_prefill_explicit_registry_param():
    """registry 파라미터 전달 시 해당 dict를 사용 (로더 호출 대체)."""
    reg = {"x": {"slug": "x", "name": "X", "category": "c",
                 "input_labels": ["a", "b"], "output_labels": ["c"]}}
    pf = prefill_contract_from_registry("x", registry=reg)
    assert pf["found"] is True
    assert pf["input_fields"] == ["a", "b"]
    assert pf["output_fields"] == ["c"]


# ── C. Loader save→load 왕복 ────────────────────────────────────────────────


def test_contract_instance_save_load_roundtrip(tmp_path, monkeypatch):
    """save → load: 핵심 필드가 동일하게 복원된다."""
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    _save_contract_instance("test-calc", dict(_SAMPLE_CONTRACT))
    loaded = load_contract_instance("test-calc")
    assert loaded is not None
    assert loaded["slug"] == _SAMPLE_CONTRACT["slug"]
    assert loaded["name"] == _SAMPLE_CONTRACT["name"]
    assert loaded["input_fields"] == _SAMPLE_CONTRACT["input_fields"]
    assert loaded["output_fields"] == _SAMPLE_CONTRACT["output_fields"]
    assert loaded["formula"] == _SAMPLE_CONTRACT["formula"]
    assert loaded["formula_status"] == _SAMPLE_CONTRACT["formula_status"]
    assert loaded["test_cases"] == _SAMPLE_CONTRACT["test_cases"]
    assert loaded["legal_refs"] == _SAMPLE_CONTRACT["legal_refs"]
    assert loaded["desc"] == _SAMPLE_CONTRACT["desc"]
    assert "generated_at" in loaded


def test_load_contract_registry_after_save(tmp_path, monkeypatch):
    """save 후 load_contract_registry()에 calc_slug 인덱스가 기록된다."""
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    assert load_contract_registry() == {}
    _save_contract_instance("test-calc", dict(_SAMPLE_CONTRACT))
    idx = load_contract_registry()
    assert "test-calc" in idx
    assert idx["test-calc"]["contract_slug"] == "test-calc"
    assert idx["test-calc"]["formula_status"] == "operator_confirmed"
    assert idx["test-calc"]["test_cases_status"] == "operator_confirmed"
    assert idx["test-calc"]["generated_at"]


# ── D. Loader 안전성 ────────────────────────────────────────────────────────


def test_load_contract_instance_missing_file(tmp_path, monkeypatch):
    """파일 없음 → None (예외나 빈 Contract 없음)."""
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    assert load_contract_instance("no-instance") is None


def test_load_contract_instance_malformed_yaml(tmp_path, monkeypatch):
    """YAML malformed → ValueError (명확한 오류)."""
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    inst_dir = tmp_path / "schema" / "instances"
    inst_dir.mkdir(parents=True)
    (inst_dir / "bad.yaml").write_text("{{{{ not yaml", encoding="utf-8")
    with pytest.raises(ValueError, match="파싱 실패"):
        load_contract_instance("bad")


def test_load_contract_instance_invalid_structure(tmp_path, monkeypatch):
    """YAML이 dict가 아니면 ValueError (빈 Contract 반환 금지)."""
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    inst_dir = tmp_path / "schema" / "instances"
    inst_dir.mkdir(parents=True)
    (inst_dir / "list.yaml").write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(ValueError, match="구조가 올바르지"):
        load_contract_instance("list")


@pytest.mark.parametrize("bad_slug", ["../etc/passwd", "a/b", "a\\b", "..", "a..b", ""])
def test_load_contract_instance_path_traversal(bad_slug, tmp_path, monkeypatch):
    """path traversal slug → ValueError (외부 입력을 파일 경로로 사용 금지)."""
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    with pytest.raises(ValueError):
        load_contract_instance(bad_slug)


def test_load_contract_registry_malformed(tmp_path, monkeypatch):
    """registry.yaml malformed → ValueError."""
    monkeypatch.setattr("modules.app_factory._SCHEMA_DIR", tmp_path / "schema")
    (tmp_path / "schema").mkdir(parents=True)
    (tmp_path / "schema" / "registry.yaml").write_text("{{{{ bad", encoding="utf-8")
    with pytest.raises(ValueError, match="파싱 실패"):
        load_contract_registry()
