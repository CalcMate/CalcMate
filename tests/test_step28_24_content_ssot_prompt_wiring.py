# -*- coding: utf-8 -*-
"""tests/test_step28_24_content_ssot_prompt_wiring.py — STEP 28-24 회귀 테스트.

STEP 28-23에서 확인된 두 AI 콘텐츠 생성 경로(writer.py / calculator_pipeline.py)의
SSOT 미연결 문제를 STEP 28-24에서 배선한 것에 대한 production wiring regression test.
실제 AI API는 호출하지 않는다(전부 mock).
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import content.calculator.writer as W
import modules.law_ssot as LS
from modules.calculator_pipeline import _legal_basis_block


def _mocked_auto_generate_all(calc, capture, fake_master=None):
    """AI/SEO/FAQ/이미지 전부 mock 처리하고 최종 prompt에 전달되는 law_ssot_block만 캡처."""
    orig = W.PM.get_article_prompt

    def spy(*args, **kwargs):
        capture["law_ssot_block"] = kwargs.get("law_ssot_block")
        return orig(*args, **kwargs)

    fake_provider = MagicMock()
    fake_provider.chat.return_value = ("<h2>mock</h2>", 100)

    patches = [
        patch.object(W.PM, "get_article_prompt", side_effect=spy),
        patch.object(W, "build_provider_for_role", return_value=(fake_provider, "fake-model")),
        patch.object(W, "generate_faq", return_value=[]),
        patch.object(W, "_seo_pair", return_value={"seo_title": "t", "seo_description": "d"}),
        patch.object(W, "_image_pair", return_value={"thumbnail": "", "body": ""}),
    ]
    if fake_master is not None:
        patches.append(patch.object(LS, "_load_master", return_value=fake_master))

    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        if fake_master is not None:
            with patches[5]:
                W.auto_generate_all({"OPENAI_API_KEY": "fake"}, calc, save=False, auto_review=False)
        else:
            W.auto_generate_all({"OPENAI_API_KEY": "fake"}, calc, save=False, auto_review=False)


class TestWriterPathWiring:
    """Test 1/2: writer 경로(auto_generate_all -> generate_article -> get_article_prompt)."""

    def test_law_ssot_block_reaches_final_prompt(self):
        capture = {}
        calc = {"slug": "unemployment-benefit", "name": "실업급여 계산기", "id": None}
        _mocked_auto_generate_all(calc, capture)
        assert capture.get("law_ssot_block")
        assert "68,100" in capture["law_ssot_block"]

    def test_mock_ssot_change_reflected_in_final_prompt(self):
        capture = {}
        fake_master = {
            "unemployment-benefit": {
                "content_ssot": {
                    "effective_year": 2099,
                    "items": [{"item": "TEST_ITEM", "value": "99999원", "legal_basis": "TEST_LAW"}],
                }
            }
        }
        calc = {"slug": "unemployment-benefit", "name": "실업급여 계산기", "id": None}
        _mocked_auto_generate_all(calc, capture, fake_master=fake_master)
        assert "99999원" in capture["law_ssot_block"]
        assert "68,100" not in capture["law_ssot_block"]


class TestCalculatorPipelinePathWiring:
    """Test 3/4: calculator_pipeline 경로(_legal_basis_block -> content_ssot)."""

    def test_content_ssot_included_in_final_prompt(self):
        block = _legal_basis_block({"slug": "unemployment-benefit"})
        assert "68,100" in block
        assert "[2026년 현행 법정수치" in block or "현행 법정수치" in block

    def test_mock_ssot_change_reflected_in_calculator_pipeline_prompt(self):
        fake_master = {
            "unemployment-benefit": {
                "law": "고용보험법", "article": "제40조", "authority": "고용노동부",
                "content_ssot": {
                    "effective_year": 2099,
                    "items": [{"item": "TEST_ITEM", "value": "88888원", "legal_basis": "TEST_LAW"}],
                },
            }
        }
        with patch.object(LS, "_load_master", return_value=fake_master):
            block = _legal_basis_block({"slug": "unemployment-benefit"})
        assert "88888원" in block
        # 법령 인용 가드레일도 함께 유지되어야 한다(기존 역할 보존).
        assert "고용보험법" in block


class TestNoContentSsotIsNoOp:
    """Test 5: content_ssot가 없는 slug는 기존과 같이 빈 block/no-op."""

    def test_writer_path_empty_block_for_slug_without_content_ssot(self):
        capture = {}
        calc = {"slug": "weekly-holiday-allowance", "name": "주휴수당 계산기", "id": None}
        _mocked_auto_generate_all(calc, capture)
        assert capture.get("law_ssot_block") == ""

    def test_calculator_pipeline_path_unchanged_for_slug_without_content_ssot(self):
        block = _legal_basis_block({"slug": "weekly-holiday-allowance"})
        # content_ssot가 없으므로 "현행 법정수치" 섹션 자체가 붙지 않아야 한다.
        assert "현행 법정수치" not in block
        assert "근로기준법" in block  # 기존 법령 인용 가드레일은 그대로 유지


class TestCalculationUnchanged:
    """Test 6: 이번 STEP은 프롬프트 wiring만 변경 — 계산 로직/공식은 절대 변경되지 않아야 한다."""

    def test_compute_js_untouched(self):
        import modules.app_generator as AG

        js = AG._compute_js({"slug": "unemployment-benefit"})
        assert "68100" in js and "66048" in js

    def test_four_insurances_compute_untouched(self):
        import modules.app_generator as AG

        js = AG._compute_js({"slug": "four-insurances"})
        assert "410000" in js and "6590000" in js and "0.0475" in js
