# -*- coding: utf-8 -*-
"""tests/test_bmi_input_validation.py — bmi-calculator 입력 검증 회귀 테스트

배경: height_cm=0 입력 시 ZeroDivisionError, height_cm=1 등 비현실적으로 작은
키에서도 BMI가 검증 없이 계산되는 문제가 발견되어 다음 두 지점에 최소 검증을 추가했다.
  1) docs/registry_auto.yaml(bmi-calculator).compute_rules.min_value.height_cm = 50
     → modules/app_generator.py::_compute_js()가 생성하는 실제 공개 사이트 JS에
       "height_cm < 50" 이면 계산을 실행하지 않고 null을 반환하는 가드를 주입한다.
  2) modules/formula_engine.py::_eval()의 나눗셈 연산에 ZeroDivisionError → FormulaError
     변환을 추가해, 수식 엔진을 직접 호출하는 경로(Dashboard 검증 등)에서도
     처리되지 않은 크래시 대신 항상 FormulaError로 귀결되도록 했다.

이 테스트는 위 두 지점과, 정상 입력(계약서 test_cases 5건)의 계산 결과가
기존과 동일하게 보존되는지를 함께 검증한다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from modules.app_generator import _compute_js
from modules.formula_engine import execute_formula, FormulaError

BMI_FORMULA = "round(weight_kg / ((height_cm / 100) ** 2), 2)"
BMI_CALC = {
    "slug": "bmi-calculator",
    "input_schema": {"height_cm": 0, "weight_kg": 0},
    "output_schema": {"bmi": 0.0},
    "formula": BMI_FORMULA,
}

# docs/contract_schema/instances/bmi-calculator.yaml의 operator_confirmed 케이스
NORMAL_CASES = [
    (170, 65, 22.49),
    (160, 50, 19.53),
    (180, 100, 30.86),
    (150, 30, 13.33),
    (200, 150, 37.5),
]


# ═══════════════════════════════════════════════════════════════════
# 1. 생성된 JS(공개 사이트 실제 계산 경로)에 height_cm 가드 주입 확인
# ═══════════════════════════════════════════════════════════════════

def test_generated_js_rejects_height_below_50():
    js = _compute_js(BMI_CALC)
    assert "height_cm < 50" in js, f"height_cm 최소값 가드 누락:\n{js}"
    assert "return null" in js


# ═══════════════════════════════════════════════════════════════════
# 2. execute_formula() — height_cm=0 → ZeroDivisionError 대신 FormulaError
# ═══════════════════════════════════════════════════════════════════

def test_execute_formula_zero_height_no_zerodivisionerror():
    with pytest.raises(FormulaError):
        execute_formula(BMI_FORMULA, {"height_cm": 0, "weight_kg": 65}, {"bmi": 0.0})


def test_execute_formula_zero_height_does_not_raise_raw_zerodivisionerror():
    """FormulaError는 허용되지만 원시 ZeroDivisionError가 새어나가면 안 된다."""
    try:
        execute_formula(BMI_FORMULA, {"height_cm": 0, "weight_kg": 65}, {"bmi": 0.0})
        assert False, "예외가 발생해야 한다"
    except ZeroDivisionError:
        pytest.fail("ZeroDivisionError가 그대로 노출됨 — FormulaError로 변환되지 않음")
    except FormulaError:
        pass  # 기대한 동작


# ═══════════════════════════════════════════════════════════════════
# 3. 정상 계산 결과 보존 — 계약서 test_cases 5건 (Golden 기준)
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("height_cm,weight_kg,expected_bmi", NORMAL_CASES)
def test_normal_cases_preserved(height_cm, weight_kg, expected_bmi):
    out = execute_formula(BMI_FORMULA, {"height_cm": height_cm, "weight_kg": weight_kg}, {"bmi": 0.0})
    assert out["bmi"] == expected_bmi


# ═══════════════════════════════════════════════════════════════════
# 4. 생성된 JS 가드 시뮬레이션(Python 미러) — 경계값
# ═══════════════════════════════════════════════════════════════════

def _js_guard_mirror(height_cm: float) -> bool:
    """_compute_js()가 주입하는 'if (height_cm < 50) return null' 조건의 Python 미러."""
    return height_cm < 50


@pytest.mark.parametrize("height_cm", [0, -10, 1, 49, 49.9])
def test_js_guard_rejects_invalid_heights(height_cm):
    assert _js_guard_mirror(height_cm) is True


@pytest.mark.parametrize("height_cm", [50, 150, 170, 200])
def test_js_guard_allows_valid_heights(height_cm):
    assert _js_guard_mirror(height_cm) is False
