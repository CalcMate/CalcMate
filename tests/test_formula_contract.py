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
