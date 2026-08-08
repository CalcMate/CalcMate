# -*- coding: utf-8 -*-
"""tests/test_jeonse_vs_monthly.py — 전세 vs 월세 비교 계산기 formula dict 회귀 테스트

공식 3개 (주택임대차보호법 제7조의2 + 시행령 제9조):
  jeonse_opp_cost       = (jeonse_deposit - wolse_deposit) * rate / 100 / 12
  wolse_to_jeonse_equiv = wolse_deposit + wolse_amount * 1200 / rate
  monthly_savings       = wolse_amount - (jeonse_deposit - wolse_deposit) * rate / 100 / 12

기본값: rate=4.75% (2026-08 기준금리 2.75% + 시행령 가산이율 2%)
경계규칙: rate <= 0 → 계산 불가 (None 반환)
단위: 만원/%, 출력 소수점 2자리 반올림
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from modules.formula_engine import execute_formula

_FORMULA = {
    "jeonse_opp_cost":       "(jeonse_deposit - wolse_deposit) * rate / 100 / 12",
    "wolse_to_jeonse_equiv": "wolse_deposit + wolse_amount * 1200 / rate",
    "monthly_savings":       "wolse_amount - (jeonse_deposit - wolse_deposit) * rate / 100 / 12",
}

_SCHEMA = {
    "jeonse_deposit": "number",
    "wolse_deposit":  "number",
    "wolse_amount":   "number",
    "rate":           "number",
}


def _calc(jeonse_deposit, wolse_deposit, wolse_amount, rate):
    inputs = dict(
        jeonse_deposit=jeonse_deposit,
        wolse_deposit=wolse_deposit,
        wolse_amount=wolse_amount,
        rate=rate,
    )
    if rate <= 0:
        return None
    result = execute_formula(_FORMULA, inputs, _SCHEMA)
    return {k: round(v, 2) for k, v in result.items()}


# ─── TC-1: 월세 유리 케이스 ───────────────────────────────────────────────────
def test_tc1_wolse_favorable():
    """J=3억, D=5000만, W=80만, R=4.75% → 전세 기회비용(98.96) > 월세 → 월세 유리."""
    r = _calc(30000, 5000, 80, 4.75)
    assert r is not None
    assert abs(r["jeonse_opp_cost"] - 98.96) < 0.01
    assert abs(r["wolse_to_jeonse_equiv"] - 25211) < 1
    assert abs(r["monthly_savings"] - (-18.96)) < 0.01
    assert r["monthly_savings"] < 0  # 음수 → 월세 유리


# ─── TC-2: 전세 유리 케이스 ───────────────────────────────────────────────────
def test_tc2_jeonse_favorable():
    """J=3억, D=5000만, W=100만, R=4.75% → 월세가 기회비용보다 크므로 전세 유리."""
    r = _calc(30000, 5000, 100, 4.75)
    assert r is not None
    assert abs(r["jeonse_opp_cost"] - 98.96) < 0.01
    assert abs(r["wolse_to_jeonse_equiv"] - 30263) < 1
    assert abs(r["monthly_savings"] - 1.04) < 0.01
    assert r["monthly_savings"] > 0  # 양수 → 전세 유리


# ─── TC-3: 5% 전환율 ──────────────────────────────────────────────────────────
def test_tc3_rate_5pct():
    """J=5억, D=1억, W=150만, R=5.0% — 순수 사칙연산 검증."""
    r = _calc(50000, 10000, 150, 5.0)
    assert r is not None
    assert abs(r["jeonse_opp_cost"] - 166.67) < 0.01
    assert abs(r["wolse_to_jeonse_equiv"] - 46000) < 1
    assert abs(r["monthly_savings"] - (-16.67)) < 0.01


# ─── TC-4: 소형/빌라 케이스 ───────────────────────────────────────────────────
def test_tc4_small_property():
    """J=2억, D=3000만, W=80만, R=4.75% — 소형 주택 전형."""
    r = _calc(20000, 3000, 80, 4.75)
    assert r is not None
    assert abs(r["jeonse_opp_cost"] - 67.29) < 0.01
    assert abs(r["wolse_to_jeonse_equiv"] - 23211) < 1
    assert abs(r["monthly_savings"] - 12.71) < 0.01


# ─── TC-5: 순수 전세 vs 순월세 ───────────────────────────────────────────────
def test_tc5_pure_jeonse_vs_pure_wolse():
    """J=1억, D=0(보증금 없는 순월세), W=40만, R=4.75%."""
    r = _calc(10000, 0, 40, 4.75)
    assert r is not None
    assert abs(r["jeonse_opp_cost"] - 39.58) < 0.01
    assert abs(r["wolse_to_jeonse_equiv"] - 10105) < 1
    assert abs(r["monthly_savings"] - 0.42) < 0.01


# ─── TC-6: 보증금 동일 경계 ───────────────────────────────────────────────────
def test_tc6_equal_deposit_boundary():
    """J=D=2억 — 차이가 0이므로 기회비용=0, monthly_savings=wolse_amount."""
    r = _calc(20000, 20000, 60, 4.75)
    assert r is not None
    assert abs(r["jeonse_opp_cost"] - 0.0) < 0.01
    assert abs(r["monthly_savings"] - 60.0) < 0.01


# ─── TC-7: rate=0 → 계산 불가 ─────────────────────────────────────────────────
def test_tc7_rate_zero_returns_none():
    """rate=0 → wolse_to_jeonse_equiv 분모=0, 계산 불가."""
    r = _calc(30000, 5000, 80, 0)
    assert r is None


# ─── 경계: rate 음수 → 계산 불가 ──────────────────────────────────────────────
def test_negative_rate_returns_none():
    """rate<0 → 계산 불가 (positive_inputs 규칙)."""
    r = _calc(30000, 5000, 80, -1)
    assert r is None


# ─── compute_rules → _compute_js rate<=0 null 반환 검증 ──────────────────────
def test_compute_js_generates_rate_guard():
    """_compute_js()가 compute_rules.positive_inputs=['rate']에서
    'if (rate <= 0) { return null; }' 라인을 생성하는지 확인."""
    from modules.app_generator import _compute_js
    from modules.registry_loader import load_registry

    reg = load_registry(force=True)
    calc = reg.get("jeonse-vs-monthly")
    assert calc is not None, "jeonse-vs-monthly가 registry에 없음"
    js = _compute_js(calc)
    assert "if (rate <= 0) { return null; }" in js, (
        f"rate 가드 라인이 없음:\n{js}"
    )


# ─── v3 Registry READY 상태 확인 ──────────────────────────────────────────────
def test_v3_registry_status_ready():
    """v3 Registry의 jeonse-vs-monthly status=READY, source=app_factory."""
    from modules.registry_loader import load_registry_v3

    v3 = load_registry_v3(force=True)
    entry = v3.get("jeonse-vs-monthly")
    assert entry is not None, "v3 Registry에 jeonse-vs-monthly 없음"
    assert entry.get("status") == "READY"
    assert entry.get("source") == "app_factory"
    assert entry.get("tier") == 2
    assert entry.get("compute_rules") == {"positive_inputs": ["rate"]}


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
