# -*- coding: utf-8 -*-
"""tests/test_review_center.py — Phase3-3 검토센터 핵심 로직 테스트

검증 범위:
  - extract_checklist(): 규칙 기반 항목 추출 (D-2 카테고리 로직 포함)
  - detect_tier2b_keywords(): Tier2-B 키워드 감지
  - check_slug_conflict(): slug 중복 감지
  - pre_build_qa(): 6단계 QA (결함 있는 계산기로 실패 감지)
  - promote_to_ready() 체크리스트 검증 (미완료 시 차단)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from modules.review_center import extract_checklist, detect_tier2b_keywords, CRITICAL_CATEGORIES


# ─────────────────────────────────────────────────────────────
# 1. extract_checklist — 항목 추출 로직
# ─────────────────────────────────────────────────────────────

def _make_app(formula=None, legal_refs=None, category="", compute_rules=None,
              input_schema=None, seo_title=None, faq=None):
    return {
        "formula": formula or "",
        "legal_refs": legal_refs or [],
        "category": category,
        "compute_rules": compute_rules or {},
        "input_schema": input_schema or {},
        "seo_title": seo_title or "",
        "faq": faq or [],
    }


def test_formula_accuracy_extracted_for_tier2a():
    """Tier2-A + formula 있으면 formula_accuracy 항목 추출."""
    app = _make_app(formula="gross * 0.033")
    items = extract_checklist(app, tier="Tier2-A", category="세금/세법")
    ids = [i["id"] for i in items]
    assert "formula_accuracy" in ids, f"formula_accuracy 누락. 항목: {ids}"


def test_formula_accuracy_not_extracted_for_tier2b():
    """Tier2-B에서는 formula_accuracy 항목을 추출하지 않음."""
    app = _make_app(formula="days * rate", input_schema={"start_date": {"type": "date"}})
    items = extract_checklist(app, tier="Tier2-B", category="병역/공무")
    ids = [i["id"] for i in items]
    assert "formula_accuracy" not in ids, "Tier2-B에서 formula_accuracy 추출됨 (오류)"


def test_legal_basis_critical_for_critical_category():
    """법령 카테고리 계산기에서 legal_basis는 🔴 필수."""
    for cat in ["세금/세법", "노동/고용법", "복지/사회보험", "병역/공무", "세금/정부혜택"]:
        app = _make_app(formula="a * b", category=cat)
        items = extract_checklist(app, tier="Tier2-A", category=cat)
        lb = next((i for i in items if i["id"] == "legal_basis"), None)
        assert lb is not None, f"legal_basis 없음 (category={cat})"
        assert lb["severity"] == "critical", f"severity가 critical이 아님 (category={cat}): {lb['severity']}"


def test_legal_basis_advisory_for_noncritical_category():
    """순수 산술/부동산 카테고리에서 legal_basis는 🟡 권장."""
    app = _make_app(formula="a * b", category="부동산/임대")
    items = extract_checklist(app, tier="Tier2-A", category="부동산/임대")
    lb = next((i for i in items if i["id"] == "legal_basis"), None)
    assert lb is not None, "legal_basis 없음"
    assert lb["severity"] == "advisory", f"severity가 advisory가 아님: {lb['severity']}"


def test_legal_basis_critical_when_no_category():
    """카테고리 미지정(None/빈문자열)이면 legal_basis는 보수적으로 🔴 필수."""
    for cat in ["", None]:
        app = _make_app(formula="a * b", category=cat or "")
        items = extract_checklist(app, tier="Tier2-A", category=cat or "")
        lb = next((i for i in items if i["id"] == "legal_basis"), None)
        assert lb is not None
        assert lb["severity"] == "critical", f"빈 카테고리에서 critical이 아님: {lb['severity']}"


def test_legal_refs_empty_shows_warning():
    """legal_refs 미입력 시 display_value에 경고 표시."""
    app = _make_app(formula="a * b", legal_refs=[], category="세금/세법")
    items = extract_checklist(app, tier="Tier2-A", category="세금/세법")
    lb = next((i for i in items if i["id"] == "legal_basis"), None)
    assert lb is not None
    assert "미입력" in lb["display_value"] or "⚠️" in lb["display_value"], \
        f"경고 표시 없음: {lb['display_value']}"


def test_legal_refs_present_shows_refs():
    """legal_refs 있을 시 display_value에 ref 값 표시."""
    app = _make_app(formula="a * b", legal_refs=["소득세법 제127조"], category="세금/세법")
    items = extract_checklist(app, tier="Tier2-A", category="세금/세법")
    lb = next((i for i in items if i["id"] == "legal_basis"), None)
    assert lb is not None
    assert "소득세법" in lb["display_value"], f"법령 내용 미표시: {lb['display_value']}"


def test_rate_constant_extracted_for_decimal_in_formula():
    """공식에 소수점 상수가 있으면 rate_constant 추출."""
    app = _make_app(formula="income * 0.033", category="세금/세법")
    items = extract_checklist(app, tier="Tier2-A", category="세금/세법")
    ids = [i["id"] for i in items]
    assert "rate_constant" in ids, "rate_constant 누락"
    rc = next(i for i in items if i["id"] == "rate_constant")
    assert "0.033" in rc["display_value"], f"상수 미표시: {rc['display_value']}"


def test_no_rate_constant_for_integer_only_formula():
    """소수점 없는 정수만 있는 공식은 rate_constant 추출 안 함."""
    app = _make_app(formula="a * 100 / 12", category="세금/세법")
    items = extract_checklist(app, tier="Tier2-A", category="세금/세법")
    ids = [i["id"] for i in items]
    assert "rate_constant" not in ids, "정수만 있는데 rate_constant 추출됨"


def test_base_year_only_for_critical_category():
    """🔴 카테고리만 base_year 추출, 🟡 카테고리는 추출 안 함."""
    # 🔴 카테고리
    app_crit = _make_app(formula="a * b", category="노동/고용법")
    items_crit = extract_checklist(app_crit, tier="Tier2-A", category="노동/고용법")
    assert "base_year" in [i["id"] for i in items_crit], "🔴 카테고리에서 base_year 누락"
    # 🟡 카테고리
    app_adv = _make_app(formula="a * b", category="부동산/임대")
    items_adv = extract_checklist(app_adv, tier="Tier2-A", category="부동산/임대")
    assert "base_year" not in [i["id"] for i in items_adv], "🟡 카테고리에서 base_year 추출됨"


def test_default_values_extracted_when_present():
    """input_schema에 default 있으면 default_values 추출."""
    app = _make_app(input_schema={"rate": {"type": "number", "default": 4.75}},
                    formula="a * b", category="부동산/임대")
    items = extract_checklist(app, tier="Tier2-A", category="부동산/임대")
    ids = [i["id"] for i in items]
    assert "default_values" in ids, "default_values 누락"


def test_seo_faq_advisory():
    """seo_title/faq가 있으면 🟡 권장 항목으로 추출."""
    app = _make_app(formula="a * b", seo_title="테스트 계산기",
                    faq=[{"q": "Q1", "a": "A1"}], category="부동산/임대")
    items = extract_checklist(app, tier="Tier2-A", category="부동산/임대")
    adv_ids = [i["id"] for i in items if i.get("severity") == "advisory"]
    assert "seo_title" in adv_ids, "seo_title advisory 항목 누락"
    assert "faq_content" in adv_ids, "faq_content advisory 항목 누락"


def test_all_items_unchecked_by_default():
    """추출된 모든 항목은 초기에 checked=False."""
    app = _make_app(formula="income * 0.033", legal_refs=[], category="세금/세법",
                    seo_title="테스트", faq=[{"q": "Q", "a": "A"}])
    items = extract_checklist(app, tier="Tier2-A", category="세금/세법")
    assert items, "항목이 없음"
    for item in items:
        assert not item["checked"], f"'{item['id']}' 항목이 초기에 checked=True"
        assert item["checked_by"] is None
        assert item["checked_at"] is None


# ─────────────────────────────────────────────────────────────
# 1-b. formula_cap 항목 추출 (HOLD-3 수정 연동)
# ─────────────────────────────────────────────────────────────

def test_formula_cap_extracted_when_min_max_present():
    """formula에 min()/max()가 있으면 formula_cap 🔴 항목 추출."""
    app = _make_app(
        formula="15 + min(max(0, (years_of_service - 1) // 2), 10)",
        category="노동/고용법",
        input_schema={"years_of_service": {"type": "number"}},
    )
    items = extract_checklist(app, tier="Tier2-A", category="노동/고용법")
    ids = [i["id"] for i in items]
    assert "formula_cap" in ids, f"formula_cap 누락. 항목: {ids}"
    cap = next(i for i in items if i["id"] == "formula_cap")
    assert cap["severity"] == "critical", f"formula_cap이 critical이 아님: {cap['severity']}"
    assert "min" in cap["display_value"] or "max" in cap["display_value"], \
        f"display_value에 cap 함수 미표시: {cap['display_value']}"
    # display_value에 실제 formula 문자열 포함 확인
    assert "years_of_service" in cap["display_value"], "display_value에 formula 미포함"


def test_formula_cap_not_extracted_when_no_cap_function():
    """min()/max() 없는 formula에서는 formula_cap 미발생."""
    app = _make_app(formula="income * 0.033", category="세금/세법")
    items = extract_checklist(app, tier="Tier2-A", category="세금/세법")
    ids = [i["id"] for i in items]
    assert "formula_cap" not in ids, "min/max 없는데 formula_cap 추출됨"


def test_formula_cap_not_extracted_for_date_based():
    """date_based 계산기에서는 formula_cap 미발생."""
    app = _make_app(formula="min(a, b)", category="노동/고용법")
    app["compute_type"] = "date_based"
    items = extract_checklist(app, tier="Tier2-B", category="노동/고용법")
    ids = [i["id"] for i in items]
    assert "formula_cap" not in ids, "date_based에서 formula_cap 추출됨"


def test_formula_cap_and_legal_basis_are_independent():
    """formula_cap과 legal_basis는 독립적으로 각각 추출되어야 한다."""
    app = _make_app(
        formula="15 + min(max(0, (years_of_service - 1) // 2), 10)",
        category="노동/고용법",
        legal_refs=["근로기준법 제60조"],
        input_schema={"years_of_service": {"type": "number"}},
    )
    items = extract_checklist(app, tier="Tier2-A", category="노동/고용법")
    ids = [i["id"] for i in items]
    assert "formula_cap" in ids, "formula_cap 누락"
    assert "legal_basis" in ids, "legal_basis 누락"
    # 각각 checked=False로 독립 초기화
    cap = next(i for i in items if i["id"] == "formula_cap")
    lb = next(i for i in items if i["id"] == "legal_basis")
    assert not cap["checked"], "formula_cap이 checked=True로 초기화됨"
    assert not lb["checked"], "legal_basis가 checked=True로 초기화됨"


def test_formula_cap_with_dict_formula():
    """dict formula에서도 min()/max() 감지 및 formula_cap 추출."""
    import json
    app = _make_app(category="노동/고용법")
    app["formula"] = json.dumps({
        "total_days": "15 + min(max(0, (years_of_service - 1) // 2), 10)",
        "remaining_days": "15 + min(max(0, (years_of_service - 1) // 2), 10) - used_days",
    })
    app["input_schema"] = {"years_of_service": {"type": "number"}, "used_days": {"type": "number"}}
    items = extract_checklist(app, tier="Tier2-A", category="노동/고용법")
    ids = [i["id"] for i in items]
    assert "formula_cap" in ids, f"dict formula에서 formula_cap 누락. 항목: {ids}"


# ─────────────────────────────────────────────────────────────
# 2. detect_tier2b_keywords
# ─────────────────────────────────────────────────────────────

def test_detect_tier2b_keywords_positive():
    """날짜 키워드 포함 시 True."""
    assert detect_tier2b_keywords("군인 전역일 계산기"), "전역일 감지 실패"
    assert detect_tier2b_keywords("D-Day 계산기"), "d-day 감지 실패"
    assert detect_tier2b_keywords("복무 기간 계산"), "기간 감지 실패"


def test_detect_tier2b_keywords_negative():
    """일반 계산기 이름에서 False."""
    assert not detect_tier2b_keywords("원천징수 계산기"), "원천징수에서 오탐"
    assert not detect_tier2b_keywords("퇴직금 계산기"), "퇴직금에서 오탐"
    assert not detect_tier2b_keywords("전세 vs 월세 비교"), "전세vs월세에서 오탐"


# ─────────────────────────────────────────────────────────────
# 3. check_slug_conflict — 기존 9개 계산기 slug와 충돌 감지
# ─────────────────────────────────────────────────────────────

def test_slug_conflict_with_existing_registry():
    """기존 9개 계산기 slug와 충돌 시 True 반환."""
    from modules.config_loader import load_config
    cfg = load_config()
    from modules.review_center import check_slug_conflict
    # 기존 계산기 slug
    for known_slug in ["severance-pay", "freelancer-tax-3p3", "jeonse-vs-monthly"]:
        _, conflict, msg = check_slug_conflict(known_slug, cfg)
        assert conflict, f"'{known_slug}' 중복 감지 실패"
        assert known_slug in msg, f"에러 메시지에 slug 없음: {msg}"


def test_slug_no_conflict_for_new():
    """새 slug는 충돌 없음."""
    from modules.config_loader import load_config
    cfg = load_config()
    from modules.review_center import check_slug_conflict
    _, conflict, _ = check_slug_conflict("this-slug-does-not-exist-xyz-999", cfg)
    assert not conflict, "존재하지 않는 slug가 충돌로 감지됨"


# ─────────────────────────────────────────────────────────────
# 4. pre_build_qa — 결함 있는 계산기로 실패 감지
# ─────────────────────────────────────────────────────────────

def test_pre_build_qa_step1_fails_when_no_input_schema():
    """input_schema 없으면 Step 1 실패."""
    from modules.config_loader import load_config
    from modules.review_center import pre_build_qa
    cfg = load_config()
    bad_calc = {"slug": "test-bad", "input_schema": {}, "output_schema": {"result": {}}, "formula": "1+1"}
    results = pre_build_qa(bad_calc, cfg)
    step1 = next(r for r in results if r["step"] == 1)
    assert not step1["passed"], "input_schema 없는데 Step 1 통과"


def test_pre_build_qa_step2_fails_when_no_output_schema():
    """output_schema 없으면 Step 2 실패."""
    from modules.config_loader import load_config
    from modules.review_center import pre_build_qa
    cfg = load_config()
    bad_calc = {
        "slug": "test-bad",
        "input_schema": {"a": {"type": "number"}},
        "output_schema": {},
        "formula": "a * 2",
    }
    results = pre_build_qa(bad_calc, cfg)
    step2 = next(r for r in results if r["step"] == 2)
    assert not step2["passed"], "output_schema 없는데 Step 2 통과"


def test_pre_build_qa_jeonse_all_pass():
    """jeonse-vs-monthly: 기존 정상 계산기로 6단계 전체 통과."""
    from modules.config_loader import load_config
    from adapters.db.factory import get_db_adapter
    from repositories.calculator_repository import CalculatorRepository
    from modules.review_center import pre_build_qa
    cfg = load_config()
    calcs = {c["slug"]: c for c in CalculatorRepository(get_db_adapter(cfg)).get_all()}
    jeonse = calcs.get("jeonse-vs-monthly")
    if jeonse is None:
        return  # DB에 없으면 스킵
    results = pre_build_qa(jeonse, cfg)
    failed = [r for r in results if not r["passed"] and not r["skipped"]]
    assert not failed, f"jeonse-vs-monthly QA 실패: {[(r['step'], r['detail']) for r in failed]}"


def test_pre_build_qa_date_based_skips_steps_345():
    """date_based 계산기는 Step 3~5가 skip (D-4)."""
    from modules.config_loader import load_config
    from modules.review_center import pre_build_qa
    cfg = load_config()
    date_calc = {
        "slug": "test-date",
        "compute_type": "date_based",
        "input_schema": {"start_date": {"type": "date"}},
        "output_schema": {"end_date": {"label": "종료일"}},
        "formula": "",
    }
    results = pre_build_qa(date_calc, cfg)
    for step_num in [3, 4, 5]:
        step = next(r for r in results if r["step"] == step_num)
        assert step["skipped"], f"date_based에서 Step {step_num}이 skip되지 않음"


# ─────────────────────────────────────────────────────────────
# 5. promote_to_ready 체크리스트 검증
# ─────────────────────────────────────────────────────────────

def test_promote_to_ready_blocks_when_checklist_incomplete():
    """
    체크리스트 미완료 계산기에 대해 promote_to_ready()가 실패를 반환하는지.
    Registry v3에 HOLD + 미완료 checklist가 있는 경우를 mocking으로 검증.
    """
    from modules.app_factory import promote_to_ready
    from unittest.mock import patch

    mock_v3 = {
        "test-hold-calc": {
            "source": "app_factory",
            "status": "HOLD",
            "category": "세금/세법",
            "review_checklist": [
                {"id": "formula_accuracy", "severity": "critical", "label": "계산 공식", "checked": False},
                {"id": "legal_basis", "severity": "critical", "label": "법적 근거", "checked": True},
            ],
        }
    }

    with patch("modules.registry_loader.load_registry_v3", return_value=mock_v3):
        ok, msg = promote_to_ready("test-hold-calc")
    assert not ok, "미완료 체크리스트인데 promote 성공"
    assert "미완료" in msg or "필수" in msg, f"에러 메시지 부적절: {msg}"


# ── CA-2-6-1: check_hold_rules() HOLD-1 pending_validation 테스트 ────────────

from modules.app_factory import build_contract as _af_build_contract
from modules.app_factory import check_hold_rules as _af_check_hold_rules


def test_hold1_fires_for_pending_validation(monkeypatch):
    """formula_status='pending_validation' → HOLD-1 발동 (미확정 상태)."""
    monkeypatch.setattr(
        "modules.registry_loader.load_legal_master",
        lambda: {},
    )
    contract = _af_build_contract("x", "X", formula="a + b")
    assert contract["formula_status"] == "pending_validation"
    result = _af_check_hold_rules(contract)
    assert result["held"] is True
    assert "HOLD-1" in result["rules"]


def test_hold1_silent_for_operator_confirmed(monkeypatch):
    """formula_status='operator_confirmed' → HOLD-1 발동 안 됨."""
    monkeypatch.setattr(
        "modules.registry_loader.load_legal_master",
        lambda: {},
    )
    contract = _af_build_contract(
        "x", "X", formula="a + b", formula_status="operator_confirmed"
    )
    result = _af_check_hold_rules(contract)
    assert "HOLD-1" not in result["rules"]


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
