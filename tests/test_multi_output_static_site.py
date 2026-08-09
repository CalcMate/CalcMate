# -*- coding: utf-8 -*-
"""tests/test_multi_output_static_site.py — 다중출력 계산기 정적 사이트 생성 E2E 테스트

검증 범위:
  - _compute_js(): validation branch가 formula dict의 모든 출력 key를 생성하는지
  - generate_html(): EXTRA_OUTPUT_ROWS에 secondary 출력 id="out_*" 요소가 있는지
  - 단일 출력 계산기: EXTRA_OUTPUT_ROWS가 비어 있는지(회귀)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository
from modules.app_generator import _compute_js, generate_html

_cfg = load_config()
_repo = CalculatorRepository(get_db_adapter(_cfg))
_calcs = {c["slug"]: c for c in _repo.get_all()}


def _get(slug):
    c = _calcs.get(slug)
    assert c is not None, f"{slug} not found in DB"
    return c


# ─── jeonse-vs-monthly: computeResult 3출력 ───────────────────────────────────
def test_jeonse_compute_js_all_three_outputs():
    """_compute_js()가 validation branch에서 3개 출력 모두 생성해야 함."""
    js = _compute_js(_get("jeonse-vs-monthly"))
    assert 'out["jeonse_opp_cost"]' in js, "jeonse_opp_cost 누락"
    assert 'out["wolse_to_jeonse_equiv"]' in js, "wolse_to_jeonse_equiv 누락"
    assert 'out["monthly_savings"]' in js, "monthly_savings 누락"


def test_jeonse_compute_js_rate_guard():
    """rate <= 0 가드가 유지되어야 함."""
    js = _compute_js(_get("jeonse-vs-monthly"))
    assert "if (rate <= 0) { return null; }" in js


def test_jeonse_compute_js_output_order():
    """출력 순서: jeonse_opp_cost → wolse_to_jeonse_equiv → monthly_savings."""
    js = _compute_js(_get("jeonse-vs-monthly"))
    i1 = js.index('out["jeonse_opp_cost"]')
    i2 = js.index('out["wolse_to_jeonse_equiv"]')
    i3 = js.index('out["monthly_savings"]')
    assert i1 < i2 < i3, "출력 순서 불일치"


# ─── jeonse-vs-monthly: index.html 3개 id="out_*" 요소 ────────────────────────
def test_jeonse_html_primary_output_id():
    """index.html에 id='out_jeonse_opp_cost'가 있어야 함."""
    html = generate_html(_get("jeonse-vs-monthly"), _cfg)
    assert 'id="out_jeonse_opp_cost"' in html


def test_jeonse_html_extra_output_ids():
    """index.html에 secondary 출력 id='out_wolse_to_jeonse_equiv', 'out_monthly_savings' 있어야 함."""
    html = generate_html(_get("jeonse-vs-monthly"), _cfg)
    assert 'id="out_wolse_to_jeonse_equiv"' in html, "wolse_to_jeonse_equiv HTML 요소 누락"
    assert 'id="out_monthly_savings"' in html, "monthly_savings HTML 요소 누락"


def test_jeonse_html_extra_result_container():
    """sm-result-extra 컨테이너가 result-card 안에 있어야 함."""
    html = generate_html(_get("jeonse-vs-monthly"), _cfg)
    rc_start = html.index('id="result-card"')
    extra_pos = html.find("sm-result-extra", rc_start)
    # sm-result-sub(id="result-formula") 위치보다 앞에 있어야 함
    sub_pos = html.find('id="result-formula"', rc_start)
    assert extra_pos != -1, "sm-result-extra 없음"
    assert extra_pos < sub_pos, "sm-result-extra가 result-formula 뒤에 있음"


# ─── freelancer-tax-3p3: 2개 출력 ─────────────────────────────────────────────
def test_freelancer_html_two_output_ids():
    """freelancer-tax-3p3 index.html에 withholding_tax + net_income id가 있어야 함."""
    html = generate_html(_get("freelancer-tax-3p3"), _cfg)
    assert 'id="out_withholding_tax"' in html, "withholding_tax HTML 요소 누락"
    assert 'id="out_net_income"' in html, "net_income HTML 요소 누락"


# ─── 단일 출력 계산기 회귀: EXTRA_OUTPUT_ROWS 없음 ───────────────────────────
def test_single_output_calc_no_extra_rows():
    """severance-pay(단일 출력)는 sm-result-extra 컨테이너가 없어야 함."""
    html = generate_html(_get("severance-pay"), _cfg)
    rc_start = html.index('id="result-card"')
    rc_end = html.find('id="result-actions"', rc_start)
    result_card_html = html[rc_start:rc_end]
    assert "sm-result-extra" not in result_card_html, "단일 출력 계산기에 sm-result-extra 삽입됨(회귀)"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
