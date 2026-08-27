# -*- coding: utf-8 -*-
"""tests/test_step28_20_ssot_wiring.py — STEP 28-20 SSOT 참조 배선 회귀 테스트.

STEP 28-19에서 확인된 구조 문제(계산 로직만 SSOT를 읽고 placeholder/Dynamic FAQ는
독립 하드코딩)를 STEP 28-20에서 SSOT 참조로 전환한 부분의 최소 회귀 테스트.
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import modules.app_generator as AG


class TestPlaceholderFollowsSsot:
    """Test A: SSOT가 바뀌면 법정수치 placeholder가 따라오는지."""

    def test_hourly_wage_placeholder_reads_ssot(self):
        fake_registry = {
            "weekly-holiday-allowance": {"compute_rules": {"min_wage": 12345}},
        }
        with patch.object(AG, "_registry", return_value=fake_registry):
            html = AG._form_fields_v2(
                {"hourly_wage": "number"}, {}, "weekly-holiday-allowance"
            )
        assert "예) 12345" in html
        assert "예) 10320" not in html

    def test_unmapped_field_keeps_existing_placeholder(self):
        """법정수치가 아닌 일반 예시값(daily_wage 등)은 SSOT와 무관하게 유지되어야 한다."""
        html = AG._form_fields_v2(
            {"daily_wage": "number"}, {}, "annual-leave-allowance"
        )
        assert 'placeholder="예) 67000"' in html


class TestDynamicFaqFollowsSsot:
    """Test B: SSOT가 바뀌면 Dynamic FAQ에 최신값이 반영되는지."""

    def test_unemployment_benefit_faq_reads_ssot(self):
        fake_registry = {
            "unemployment-benefit": {"benefit_amounts": {"daily_max": 99999}},
        }
        with patch.object(AG, "_registry", return_value=fake_registry):
            out = AG._dynamic_faq_js({"slug": "unemployment-benefit"})
        assert "99,999원" in out
        assert "68,100원" not in out

    def test_four_insurances_faq_reads_ssot(self):
        fake_registry = {
            "four-insurances": {"insurance_rates": {"np_max": 7777777, "np_min": 555555}},
        }
        with patch.object(AG, "_registry", return_value=fake_registry):
            out = AG._dynamic_faq_js({"slug": "four-insurances"})
        assert "7,777,777원" in out and "555,555원" in out


class TestIntegrityGateDetectsStaleValue:
    """Test C: stale legal value가 콘텐츠에 존재하면 G-LEGAL-CURRENT가 FAIL하는지."""

    def test_stale_value_fails_gate(self):
        from modules.content_integrity import check_g_legal_current

        fails = check_g_legal_current(
            "<p>구직급여 상한액은 66,000원입니다.</p>", "unemployment-benefit"
        )
        assert any(f["gate"] == "G-LEGAL-CURRENT" for f in fails)

    def test_current_value_passes_gate(self):
        from modules.content_integrity import check_g_legal_current

        fails = check_g_legal_current(
            "<p>구직급여 상한액은 68,100원입니다.</p>", "unemployment-benefit"
        )
        assert fails == []

    def test_generate_calculator_exposes_gate_result(self):
        """generate_calculator()가 _legal_current_passed/_legal_current_failures를 반환하는지."""
        calc = {
            "slug": "unemployment-benefit",
            "name": "실업급여 계산기",
            "input_schema": '{"avg_daily_wage": "number", "age": "number", "employment_months": "number"}',
            "output_schema": '{"daily_benefit": "number", "total_benefit": "number"}',
            "formula": "",
            "article_content": "<p>구직급여 상한액은 66,000원입니다.</p>",
        }
        files = AG.generate_calculator(calc, {})
        assert "_legal_current_passed" in files
        assert files["_legal_current_passed"] is False
        assert files["_legal_current_failures"]


class TestCalculationUnchanged:
    """Test D: 기존 계산기 계산 결과는 이번 구조개선으로 변경되지 않아야 한다."""

    def test_weekly_holiday_allowance_compute_unchanged(self):
        calc = {
            "slug": "weekly-holiday-allowance",
            "formula": "hourly_wage * (weekly_hours / 40) * 8",
            "output_schema": '{"weekly_holiday_pay": "number"}',
        }
        js = AG._compute_js(calc)
        assert "hourly_wage" in js and "weekly_hours" in js
        # 계산 공식 자체(승수/나눗셈 구조)는 그대로 유지되어야 한다.
        assert "/ 40" in js and "* 8" in js
        # 최저임금 경고 임계값은 SSOT(10320)를 따른다 — placeholder와 별개로 계산 로직은 원래도 SSOT 연동.
        assert "10320" in js

    def test_unemployment_benefit_compute_unchanged(self):
        js = AG._compute_js({"slug": "unemployment-benefit"})
        assert "68100" in js
        assert "66048" in js

    def test_four_insurances_compute_unchanged(self):
        js = AG._compute_js({"slug": "four-insurances"})
        assert "410000" in js
        assert "6590000" in js
        assert "0.0475" in js
