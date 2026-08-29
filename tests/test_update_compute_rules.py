# -*- coding: utf-8 -*-
"""tests/test_update_compute_rules.py — STEP 28-130

modules/app_factory.py::update_compute_rules(slug, rules)의 v2/v3 동시 갱신
전용 경로를 검증한다. 실제 저장소 파일(docs/registry_auto.yaml,
docs/registry/*.yaml)에는 어떤 쓰기도 발생시키지 않고, 파일 위치만
tmp_path로 격리해 함수 본문의 실제 로직(읽기 → 검증 → 쓰기)을 그대로 실행한다.

이 함수는 Validation 정책을 추론/생성하지 않는다 — 이미 결정된 rules를
정확히 두 registry에 반영하는지만 검증한다(min_value/positive_inputs 등을
이 테스트가 자동으로 만들어내지 않음).
"""
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from modules import app_factory as AF


# ── 공통 픽스처 헬퍼 ────────────────────────────────────────────────────────

def _v2_entry(**overrides):
    entry = {
        "slug": "diag-uc-calc", "name": "진단테스트 계산기", "category": "세금/세법",
        "compute_type": "single", "date_fields": [], "validation_mode": "formula",
        "field_labels": {"x": "엑스값"}, "difficulty": "simple",
        "difficulty_status": "provisional", "needs_human_legal": True,
        "law": None, "article": None, "authority": None,
    }
    entry.update(overrides)
    return entry


def _v3_meta(**overrides):
    meta = {
        "name": "진단테스트 계산기", "slug": "diag-uc-calc", "category": "세금/세법",
        "status": "HOLD", "tier": 2, "source": "app_factory",
        "review_checklist": [
            {"id": "input_validation_review", "severity": "critical",
             "label": "입력값 검증 정책 확인", "checked": False},
        ],
        "card_desc": "테스트용 카드 설명", "display_order": 99,
    }
    meta.update(overrides)
    return meta


def _setup_v2_v3(tmp_path, monkeypatch, slug="diag-uc-calc",
                  v2_entry=None, v3_meta=None, write_v2=True, write_v3=True):
    """v2(registry_auto.yaml)/v3(labor_af.yaml) 파일을 tmp_path 안에 준비하고,
    관련 경로/로더를 전부 tmp_path로 monkeypatch한다."""
    auto_path = tmp_path / "registry_auto.yaml"
    reg_dir = tmp_path / "registry"
    reg_dir.mkdir(parents=True, exist_ok=True)

    v2_data = {slug: v2_entry} if (write_v2 and v2_entry is not None) else {}
    auto_path.write_text(
        yaml.safe_dump(v2_data, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    v3_index = {slug: v3_meta} if (write_v3 and v3_meta is not None) else {}
    (reg_dir / "labor_af.yaml").write_text(
        yaml.safe_dump(v3_index, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    monkeypatch.setattr("modules.registry_loader._AUTO_PATH", auto_path)
    monkeypatch.setattr("modules.registry_loader.load_registry_v3",
                         lambda force=False: v3_index)
    monkeypatch.setattr("modules.registry_loader.invalidate", lambda: None)
    monkeypatch.setattr(AF, "_REG_DIR", reg_dir)

    return auto_path, reg_dir / "labor_af.yaml"


# ═══════════════════════════════════════════════════════════════════════════
# Test 1 — 정상 갱신: v2/v3 compute_rules가 동시에, 동일하게 반영됨
# ═══════════════════════════════════════════════════════════════════════════

def test_normal_update_reflects_in_both_v2_and_v3(tmp_path, monkeypatch):
    slug = "diag-uc-calc"
    auto_path, v3_path = _setup_v2_v3(tmp_path, monkeypatch, slug,
                                       v2_entry=_v2_entry(), v3_meta=_v3_meta())
    rules = {"non_negative_inputs": ["x"]}

    ok, msg = AF.update_compute_rules(slug, rules)
    assert ok, msg

    v2_after = yaml.safe_load(auto_path.read_text(encoding="utf-8"))
    v3_after = yaml.safe_load(v3_path.read_text(encoding="utf-8"))

    assert v2_after[slug]["compute_rules"] == rules
    assert v3_after[slug]["compute_rules"] == rules
    assert v2_after[slug]["compute_rules"] == v3_after[slug]["compute_rules"]


# ═══════════════════════════════════════════════════════════════════════════
# Test 2 — v2/v3 기존 데이터 보존(compute_rules 외 필드 무변경)
# ═══════════════════════════════════════════════════════════════════════════

def test_other_fields_preserved(tmp_path, monkeypatch):
    slug = "diag-uc-calc"
    v2 = _v2_entry(name="원래이름", category="원래카테고리",
                    field_labels={"x": "엑스", "y": "와이"})
    v3 = _v3_meta(name="원래이름", category="원래카테고리",
                  review_checklist=[
                      {"id": "input_validation_review", "severity": "critical",
                       "label": "입력값 검증 정책 확인", "checked": True},
                      {"id": "formula_accuracy", "severity": "critical",
                       "label": "계산 공식 정확성", "checked": True},
                  ],
                  card_desc="바뀌면 안 되는 카드 설명", display_order=7)
    auto_path, v3_path = _setup_v2_v3(tmp_path, monkeypatch, slug, v2_entry=v2, v3_meta=v3)

    ok, _ = AF.update_compute_rules(slug, {"min_value": {"x": 50}})
    assert ok

    v2_after = yaml.safe_load(auto_path.read_text(encoding="utf-8"))[slug]
    v3_after = yaml.safe_load(v3_path.read_text(encoding="utf-8"))[slug]

    # v2 보존 필드
    assert v2_after["name"] == "원래이름"
    assert v2_after["category"] == "원래카테고리"
    assert v2_after["field_labels"] == {"x": "엑스", "y": "와이"}
    assert v2_after["law"] is None
    assert v2_after["needs_human_legal"] is True

    # v3 보존 필드
    assert v3_after["name"] == "원래이름"
    assert v3_after["category"] == "원래카테고리"
    assert v3_after["status"] == "HOLD"
    assert v3_after["card_desc"] == "바뀌면 안 되는 카드 설명"
    assert v3_after["display_order"] == 7
    assert v3_after["review_checklist"] == v3["review_checklist"]  # 완전히 동일


# ═══════════════════════════════════════════════════════════════════════════
# Test 3 — v2만 존재 → v3에 없으면 v2도 쓰지 않아야 함(반쪽 갱신 방지)
# ═══════════════════════════════════════════════════════════════════════════

def test_v2_only_does_not_write_either_side(tmp_path, monkeypatch):
    slug = "diag-uc-calc"
    auto_path, v3_path = _setup_v2_v3(tmp_path, monkeypatch, slug,
                                       v2_entry=_v2_entry(), v3_meta=None, write_v3=False)
    v2_before = auto_path.read_text(encoding="utf-8")
    v3_before = v3_path.read_text(encoding="utf-8")

    with pytest.raises(ValueError):
        AF.update_compute_rules(slug, {"positive_inputs": ["x"]})

    assert auto_path.read_text(encoding="utf-8") == v2_before, "v3 없는데도 v2가 변경됨"
    assert v3_path.read_text(encoding="utf-8") == v3_before


# ═══════════════════════════════════════════════════════════════════════════
# Test 4 — v3만 존재 → v2에 없으면 v3도 쓰지 않아야 함(반쪽 갱신 방지)
# ═══════════════════════════════════════════════════════════════════════════

def test_v3_only_does_not_write_either_side(tmp_path, monkeypatch):
    slug = "diag-uc-calc"
    auto_path, v3_path = _setup_v2_v3(tmp_path, monkeypatch, slug,
                                       v2_entry=None, v3_meta=_v3_meta(), write_v2=False)
    v2_before = auto_path.read_text(encoding="utf-8")
    v3_before = v3_path.read_text(encoding="utf-8")

    with pytest.raises(ValueError):
        AF.update_compute_rules(slug, {"positive_inputs": ["x"]})

    assert auto_path.read_text(encoding="utf-8") == v2_before
    assert v3_path.read_text(encoding="utf-8") == v3_before, "v2 없는데도 v3가 변경됨"


# ═══════════════════════════════════════════════════════════════════════════
# Test 5 — 존재하지 않는 slug → 명확한 실패
# ═══════════════════════════════════════════════════════════════════════════

def test_nonexistent_slug_raises(tmp_path, monkeypatch):
    _setup_v2_v3(tmp_path, monkeypatch, "diag-uc-calc",
                 v2_entry=_v2_entry(), v3_meta=_v3_meta())
    with pytest.raises(ValueError):
        AF.update_compute_rules("this-slug-does-not-exist", {"positive_inputs": ["x"]})


# ═══════════════════════════════════════════════════════════════════════════
# Test 6 — rules가 dict가 아닌 경우 → 실패(쓰기 이전에 차단)
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("bad_rules", [None, ["positive_inputs", "x"], "positive_inputs", 123])
def test_non_dict_rules_raises_before_any_write(tmp_path, monkeypatch, bad_rules):
    slug = "diag-uc-calc"
    auto_path, v3_path = _setup_v2_v3(tmp_path, monkeypatch, slug,
                                       v2_entry=_v2_entry(), v3_meta=_v3_meta())
    v2_before = auto_path.read_text(encoding="utf-8")
    v3_before = v3_path.read_text(encoding="utf-8")

    with pytest.raises(TypeError):
        AF.update_compute_rules(slug, bad_rules)

    assert auto_path.read_text(encoding="utf-8") == v2_before
    assert v3_path.read_text(encoding="utf-8") == v3_before


# ═══════════════════════════════════════════════════════════════════════════
# Test 7 — 빈 dict({}) → 기존 "규칙 없음" 의미 유지
# ═══════════════════════════════════════════════════════════════════════════

def test_empty_dict_preserves_no_rules_semantics(tmp_path, monkeypatch):
    slug = "diag-uc-calc"
    auto_path, v3_path = _setup_v2_v3(tmp_path, monkeypatch, slug,
                                       v2_entry=_v2_entry(compute_rules={"positive_inputs": ["x"]}),
                                       v3_meta=_v3_meta(compute_rules={"positive_inputs": ["x"]}))

    ok, _ = AF.update_compute_rules(slug, {})
    assert ok

    v2_after = yaml.safe_load(auto_path.read_text(encoding="utf-8"))[slug]
    v3_after = yaml.safe_load(v3_path.read_text(encoding="utf-8"))[slug]

    # extract_checklist()/​_compute_validation_js() 등 기존 소비 코드가 전부
    # `if compute_rules:`(falsy 체크)로 판정하므로, {} 도 "규칙 없음"과 동일하게 취급됨.
    assert not v2_after["compute_rules"]
    assert not v3_after["compute_rules"]


# ═══════════════════════════════════════════════════════════════════════════
# Test 8 — 기존 계산기 회귀: 함수 추가만으로 실제 registry 데이터가 변경되지
# 않았음을 확인(이번 STEP은 실제 계산기에 함수를 적용하지 않는다 — STEP 28-130 §9)
# ═══════════════════════════════════════════════════════════════════════════

def test_real_registry_untouched_by_adding_this_function():
    """update_compute_rules()를 정의/임포트하는 것만으로 실제
    docs/registry_auto.yaml / docs/registry/*.yaml 내용이 바뀌지 않아야 한다."""
    import subprocess

    root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        ["git", "status", "--short", "--", "docs/registry_auto.yaml", "docs/registry"],
        cwd=root, capture_output=True, text=True, encoding="utf-8",
    )
    assert result.stdout.strip() == "", (
        f"실제 registry 파일이 변경됨(이번 STEP은 함수 정의만 해야 함): {result.stdout}"
    )
