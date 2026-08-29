# -*- coding: utf-8 -*-
"""tests/test_registry_validation_drift.py — STEP 28-131

v2(docs/registry_auto.yaml)와 v3(docs/registry/*_af.yaml) 사이에서 공통 필드
(compute_rules/name/category/field_labels)가 서로 달라졌는지("drift") 순수하게
탐지만 하는 governance 테스트.

이 파일은 drift를 고치지 않는다. 어느 쪽이 "맞는지" 판단하지도 않는다.
오직 "두 registry가 서로 다르다"는 사실을 구조적으로(문자열 비교가 아니라
파싱된 Python object 비교로) 탐지해 명확한 정보와 함께 실패시키는 것까지가
이 파일의 역할이다.

비교 대상은 아래 4개 공통 필드로 한정한다(v2 전용/v3 전용/DB SoT 필드는
의도적으로 제외 — STEP 28-128/130에서 이미 그 이유가 확정됨):
  compute_rules, name, category, field_labels

정규화 정책(문자열 비교나 str(dict) 비교를 쓰지 않고, 파싱된 값 자체를 비교):
  - 필드 key가 없으면 None으로 취급
  - 명시적 None도 None으로 취급(즉 key 없음과 값=None은 서로 drift가 아님)
  - {} 는 {} 그대로 유지(= None과는 다른 값 — None vs {}는 drift로 탐지됨)
  - dict/list는 파싱된 구조 그대로 == 비교(YAML key 순서 차이는 drift 아님)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

# 비교 대상 공통 필드 — v2 전용(law/article/authority/...), v3 전용(status/tier/
# review_checklist/...), DB SoT(formula/input_schema/output_schema)는 제외.
_DRIFT_FIELDS = ("compute_rules", "name", "category", "field_labels")


def detect_registry_drift(v2_data: dict, v3_data: dict, slugs=None) -> list[dict]:
    """v2/v3 registry(이미 파싱된 dict)에서 공통 필드의 drift를 탐지한다.

    v2_data / v3_data: {slug: entry_dict, ...} 형태(yaml.safe_load 결과와 동일 형태).
    slugs: 비교할 slug 목록. None이면 양쪽 키의 합집합.
    반환: [{"slug":..., "field":..., "v2":..., "v3":...}, ...] — drift 없으면 [].

    이 함수는 자동 보정을 하지 않는다 — 반환값을 읽어 사람이 판단한다.
    """
    if slugs is None:
        slugs = sorted(set(v2_data) | set(v3_data))
    drifts = []
    for slug in slugs:
        v2_entry = v2_data.get(slug) or {}
        v3_entry = v3_data.get(slug) or {}
        for field in _DRIFT_FIELDS:
            v2_val = v2_entry.get(field)  # 없으면 None — dict.get()이 정책과 정확히 일치
            v3_val = v3_entry.get(field)
            if v2_val != v3_val:
                drifts.append({"slug": slug, "field": field, "v2": v2_val, "v3": v3_val})
    return drifts


def _format_drift_report(drifts: list[dict]) -> str:
    """사람이 바로 원인을 알 수 있는 형태로 drift 목록을 포맷."""
    lines = ["Registry drift detected:"]
    for d in drifts:
        lines.append(
            f"  slug={d['slug']} field={d['field']} v2={d['v2']!r} v3={d['v3']!r}"
        )
    return "\n".join(lines)


def _assert_no_drift(v2_data: dict, v3_data: dict, slugs=None):
    drifts = detect_registry_drift(v2_data, v3_data, slugs=slugs)
    assert not drifts, _format_drift_report(drifts)


# ═══════════════════════════════════════════════════════════════════════════
# Test 1 — 정상 동일 상태: 동일 slug의 compute_rules가 v2/v3에서 완전히 같으면 PASS
# ═══════════════════════════════════════════════════════════════════════════

def test_identical_compute_rules_passes():
    v2 = {"car-tax": {"name": "자동차세", "category": "세금",
                       "field_labels": {"x": "엑스"},
                       "compute_rules": {"non_negative_inputs": ["car_price"]}}}
    v3 = {"car-tax": {"name": "자동차세", "category": "세금",
                       "field_labels": {"x": "엑스"},
                       "compute_rules": {"non_negative_inputs": ["car_price"]}}}
    _assert_no_drift(v2, v3)


def test_identical_yaml_key_order_is_not_drift():
    """YAML 파싱 후 dict 키 순서가 달라도 값이 같으면 drift 아님."""
    v2 = {"car-tax": {"compute_rules": {"a": 1, "b": 2}}}
    v3 = {"car-tax": {"compute_rules": {"b": 2, "a": 1}}}
    _assert_no_drift(v2, v3)


# ═══════════════════════════════════════════════════════════════════════════
# Test 2 — v2만 규칙 존재(v3는 빈 dict 또는 key 자체 없음) → drift 탐지
# ═══════════════════════════════════════════════════════════════════════════

def test_v2_only_rule_vs_v3_empty_dict_is_drift():
    v2 = {"car-tax": {"compute_rules": {"non_negative_inputs": ["car_price"]}}}
    v3 = {"car-tax": {"compute_rules": {}}}
    drifts = detect_registry_drift(v2, v3)
    assert len(drifts) == 1
    d = drifts[0]
    assert d["slug"] == "car-tax" and d["field"] == "compute_rules"
    assert d["v2"] == {"non_negative_inputs": ["car_price"]}
    assert d["v3"] == {}


def test_v2_only_rule_vs_v3_missing_key_is_drift():
    """실제 bmi-calculator/자동차_취등록세_계산기와 동일한 패턴(v3에 키 자체가 없음)."""
    v2 = {"bmi-calculator": {"compute_rules": {"min_value": {"height_cm": 50}}}}
    v3 = {"bmi-calculator": {}}  # compute_rules 키 없음, 다른 필드도 없음(단일 변수 격리)
    drifts = detect_registry_drift(v2, v3)
    assert len(drifts) == 1
    assert drifts[0]["field"] == "compute_rules"
    assert drifts[0]["v2"] == {"min_value": {"height_cm": 50}}
    assert drifts[0]["v3"] is None


# ═══════════════════════════════════════════════════════════════════════════
# Test 3 — v3만 규칙 존재 → drift 탐지(반대 방향도 동일하게 탐지되어야 함)
# ═══════════════════════════════════════════════════════════════════════════

def test_v3_only_rule_is_drift():
    v2 = {"car-tax": {}}  # compute_rules 키 없음
    v3 = {"car-tax": {"compute_rules": {"positive_inputs": ["rate"]}}}
    drifts = detect_registry_drift(v2, v3)
    assert len(drifts) == 1
    assert drifts[0]["field"] == "compute_rules"
    assert drifts[0]["v2"] is None
    assert drifts[0]["v3"] == {"positive_inputs": ["rate"]}


# ═══════════════════════════════════════════════════════════════════════════
# Test 4 — 규칙 내용 불일치(둘 다 규칙은 있으나 세부 값이 다름) → drift 탐지
# ═══════════════════════════════════════════════════════════════════════════

def test_content_mismatch_is_drift():
    v2 = {"car-tax": {"compute_rules": {"non_negative_inputs": ["car_price"]}}}
    v3 = {"car-tax": {"compute_rules": {"non_negative_inputs": ["car_price", "tax"]}}}
    drifts = detect_registry_drift(v2, v3)
    assert len(drifts) == 1
    assert drifts[0]["v2"] == {"non_negative_inputs": ["car_price"]}
    assert drifts[0]["v3"] == {"non_negative_inputs": ["car_price", "tax"]}


# ═══════════════════════════════════════════════════════════════════════════
# Test 5 — 규칙 종류 자체가 다름(기능적으로 유사해 보여도 동일 object가 아니면 drift)
# ═══════════════════════════════════════════════════════════════════════════

def test_different_rule_type_is_drift_even_if_functionally_similar():
    """min_value:{height_cm:50}과 non_negative_inputs:[height_cm]은 기능적으로
    비슷해 보일 수 있지만(둘 다 0/음수를 어느 정도 배제) 서로 다른 rule 종류이므로
    이 detector는 자동으로 "의미가 같다"고 판단하지 않고 그대로 drift로 취급한다."""
    v2 = {"bmi-calculator": {"compute_rules": {"min_value": {"height_cm": 50}}}}
    v3 = {"bmi-calculator": {"compute_rules": {"non_negative_inputs": ["height_cm"]}}}
    drifts = detect_registry_drift(v2, v3)
    assert len(drifts) == 1
    assert drifts[0]["v2"] != drifts[0]["v3"]


# ═══════════════════════════════════════════════════════════════════════════
# Test 6 — None / {} / key 없음 정책
# ═══════════════════════════════════════════════════════════════════════════

def test_key_missing_equals_explicit_none_not_drift():
    """key 없음과 명시적 None은 서로 drift가 아니다(둘 다 '규칙 없음'으로 정규화됨)."""
    v2 = {"x": {}}                              # compute_rules 키 없음
    v3 = {"x": {"compute_rules": None}}         # compute_rules: null
    _assert_no_drift(v2, v3)


def test_none_vs_empty_dict_is_drift():
    """None과 {}는 서로 다른 값으로 간주해 drift로 탐지해야 한다(임의로 동일 취급 금지)."""
    v2 = {"x": {}}                        # → None
    v3 = {"x": {"compute_rules": {}}}     # → {}
    drifts = detect_registry_drift(v2, v3)
    assert len(drifts) == 1
    assert drifts[0]["v2"] is None
    assert drifts[0]["v3"] == {}


def test_both_missing_is_not_drift():
    """양쪽 다 compute_rules가 없으면(annual-leave-remaining 등 실제 사례와 동일 패턴)
    둘 다 None으로 정규화되어 drift가 아니다."""
    v2 = {"annual-leave-remaining": {"name": "연차 잔여일 계산기"}}
    v3 = {"annual-leave-remaining": {"name": "연차 잔여일 계산기"}}
    _assert_no_drift(v2, v3)


# ═══════════════════════════════════════════════════════════════════════════
# Test 7 — 다른 공통 필드(name/category/field_labels) drift
# ═══════════════════════════════════════════════════════════════════════════

def test_name_drift_detected():
    v2 = {"x": {"name": "원래이름"}}
    v3 = {"x": {"name": "바뀐이름"}}
    drifts = detect_registry_drift(v2, v3)
    assert len(drifts) == 1
    assert drifts[0]["field"] == "name"
    assert drifts[0]["v2"] == "원래이름" and drifts[0]["v3"] == "바뀐이름"


def test_category_drift_detected():
    v2 = {"x": {"category": "세금"}}
    v3 = {"x": {"category": "노무/급여"}}
    drifts = detect_registry_drift(v2, v3)
    assert len(drifts) == 1
    assert drifts[0]["field"] == "category"


def test_field_labels_drift_detected():
    v2 = {"x": {"field_labels": {"a": "에이"}}}
    v3 = {"x": {"field_labels": {"a": "에이", "b": "비"}}}
    drifts = detect_registry_drift(v2, v3)
    assert len(drifts) == 1
    assert drifts[0]["field"] == "field_labels"
    assert drifts[0]["v2"] == {"a": "에이"}
    assert drifts[0]["v3"] == {"a": "에이", "b": "비"}


def test_multiple_drifts_reported_together():
    """여러 drift가 동시에 존재하면 한 번에 모두 반환되어야 한다."""
    v2 = {"x": {"name": "A", "category": "세금",
                "compute_rules": {"positive_inputs": ["r"]}}}
    v3 = {"x": {"name": "B", "category": "노무",
                "compute_rules": {}}}
    drifts = detect_registry_drift(v2, v3)
    fields = {d["field"] for d in drifts}
    assert fields == {"name", "category", "compute_rules"}
    assert len(drifts) == 3


# ═══════════════════════════════════════════════════════════════════════════
# 실제 registry 무변경 확인(이번 STEP은 테스트 코드만 추가) — 위 테스트들은 전부
# 순수 in-memory dict만 사용하므로 파일 I/O 자체가 없지만, 이중 확인 차원에서
# git status로 실제 registry 파일이 이번 STEP 동안 변경되지 않았음을 재확인한다.
# ═══════════════════════════════════════════════════════════════════════════

def test_real_registry_files_untouched():
    import subprocess

    root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        ["git", "status", "--short", "--", "docs/registry_auto.yaml", "docs/registry"],
        cwd=root, capture_output=True, text=True, encoding="utf-8",
    )
    assert result.stdout.strip() == "", (
        f"실제 registry 파일이 변경됨(이번 STEP은 탐지 테스트 코드만 추가해야 함): {result.stdout}"
    )
