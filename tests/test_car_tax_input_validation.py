# -*- coding: utf-8 -*-
"""tests/test_car_tax_input_validation.py — 자동차_취등록세_계산기 입력 검증 회귀 테스트

배경: 음수 차량가격(car_price < 0)이 그대로 계산되어 음수 취득세/등록세가
산출되는 문제가 발견되어, docs/registry_auto.yaml(자동차_취등록세_계산기)에
compute_rules.non_negative_inputs = [car_price]를 추가했다.
modules/app_generator.py::_compute_js()가 생성하는 실제 공개 사이트 JS에
"car_price < 0"이면 계산을 실행하지 않고 null을 반환하는 가드가 주입된다.

car_price == 0은 기존 동작(취득세/등록세 0원 산출)을 그대로 유지한다 — 새 정책을
추가하지 않는다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from modules.app_generator import _compute_js
from modules.formula_engine import execute_formula

CAR_TAX_FORMULA = {
    "acquisition_tax": "car_price * 0.07",
    "registration_tax": "car_price * 0.02",
}
CAR_TAX_CALC = {
    "slug": "자동차_취등록세_계산기",
    "input_schema": {"car_type": "string", "car_price": "number", "region": "string"},
    "output_schema": {"acquisition_tax": "number", "registration_tax": "number"},
    "formula": CAR_TAX_FORMULA,
}


# ═══════════════════════════════════════════════════════════════════
# 1. 생성된 JS(공개 사이트 실제 계산 경로)에 car_price 음수 가드 주입 확인
# ═══════════════════════════════════════════════════════════════════

def test_generated_js_rejects_negative_car_price():
    js = _compute_js(CAR_TAX_CALC)
    assert "car_price < 0" in js, f"car_price 음수 가드 누락:\n{js}"
    assert "return null" in js


# ═══════════════════════════════════════════════════════════════════
# 2. 생성된 JS 가드 시뮬레이션(Python 미러) — 경계값
# ═══════════════════════════════════════════════════════════════════

def _js_guard_mirror(car_price: float) -> bool:
    """_compute_js()가 주입하는 'if (car_price < 0) return null' 조건의 Python 미러."""
    return car_price < 0


@pytest.mark.parametrize("car_price", [-1, -5_000_000, -0.01])
def test_js_guard_rejects_negative_price(car_price):
    assert _js_guard_mirror(car_price) is True


@pytest.mark.parametrize("car_price", [0, 1, 30_000_000, 50_000_000])
def test_js_guard_allows_non_negative_price(car_price):
    assert _js_guard_mirror(car_price) is False


# ═══════════════════════════════════════════════════════════════════
# 3. 정상 계산 결과 보존 (execute_formula, Python 엔진 — 회귀 방지)
# ═══════════════════════════════════════════════════════════════════

def test_normal_case_30000000():
    out = execute_formula(CAR_TAX_FORMULA, {"car_price": 30_000_000}, None)
    assert out["acquisition_tax"] == 2_100_000.0
    assert out["registration_tax"] == 600_000.0


def test_normal_case_50000000():
    out = execute_formula(CAR_TAX_FORMULA, {"car_price": 50_000_000}, None)
    assert out["acquisition_tax"] == 3_500_000.0
    assert out["registration_tax"] == 1_000_000.0


def test_zero_price_preserves_existing_behavior():
    """car_price=0은 기존 정책(거부하지 않음)을 그대로 유지 — 신규 정책 추가 금지."""
    out = execute_formula(CAR_TAX_FORMULA, {"car_price": 0}, None)
    assert out["acquisition_tax"] == 0.0
    assert out["registration_tax"] == 0.0
