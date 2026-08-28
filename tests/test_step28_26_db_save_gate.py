# -*- coding: utf-8 -*-
"""tests/test_step28_26_db_save_gate.py — STEP 28-26 회귀 테스트.

DB 저장 직전 G-LEGAL-CURRENT 검증(논블로킹 warning) 배선에 대한 regression test.
실제 DB에 UPDATE/INSERT를 실행하지 않는다(전부 mock repository 사용).
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import content.calculator.writer as W
from modules.calculator_pipeline import _check_legal_current_before_save
from modules.content_integrity import check_g_legal_current


class FakeRepo:
    """실제 DB에 접근하지 않는 mock repository. update_generated 호출 인자만 캡처."""

    def __init__(self, db=None):
        self.calls = []

    def update_generated(self, cid, data):
        self.calls.append((cid, dict(data)))


def _run_writer(article_html, capture_repo):
    fake_provider = MagicMock()
    fake_provider.chat.return_value = (article_html, 100)
    with patch.object(W, "build_provider_for_role", return_value=(fake_provider, "fake-model")), \
         patch.object(W, "generate_faq", return_value=[]), \
         patch.object(W, "_seo_pair", return_value={"seo_title": "t", "seo_description": "d"}), \
         patch.object(W, "_image_pair", return_value={"thumbnail": "", "body": ""}), \
         patch("repositories.calculator_repository.CalculatorRepository", return_value=capture_repo):
        calc = {"slug": "unemployment-benefit", "name": "실업급여 계산기", "id": "test-id"}
        return W.auto_generate_all({"OPENAI_API_KEY": "fake"}, calc, save=True, auto_review=False)


class TestWriterPathSaveGate:
    """Test A/B: writer 경로의 DB 저장 직전 게이트."""

    def test_pass_case_saves_normally(self):
        repo = FakeRepo()
        res = _run_writer("<p>구직급여 상한액은 68,100원입니다.</p>", repo)
        assert res["_legal_current_passed"] is True
        assert res["_legal_current_failures"] == []
        assert res["_saved"] is True
        assert len(repo.calls) == 1  # DB 저장이 정상 실행됨

    def test_fail_case_still_saves_with_warning(self):
        repo = FakeRepo()
        res = _run_writer("<p>구직급여 상한액은 66,000원입니다.</p>", repo)
        assert res["_legal_current_passed"] is False
        assert res["_legal_current_failures"]  # 실패 상세가 기록됨
        # 논블로킹 정책 — 저장은 그대로 진행되어야 한다.
        assert res["_saved"] is True
        assert len(repo.calls) == 1
        cid, payload = repo.calls[0]
        assert "66,000원" in payload["article_content"]  # 차단되지 않고 그대로 저장됨

    def test_db_payload_excludes_internal_meta_keys(self):
        """_legal_current_* 는 내부 메타이므로 실제 DB payload에 섞여 들어가면 안 된다."""
        repo = FakeRepo()
        _run_writer("<p>구직급여 상한액은 68,100원입니다.</p>", repo)
        _, payload = repo.calls[0]
        assert "_legal_current_passed" not in payload
        assert "_legal_current_failures" not in payload


class TestCalculatorPipelineSaveGate:
    """Test C/D: calculator_pipeline 경로의 DB 저장 직전 게이트(헬퍼 함수 단위 테스트)."""

    def test_pass_case(self):
        fails = _check_legal_current_before_save(
            "<p>구직급여 상한액은 68,100원입니다.</p>", "unemployment-benefit", "cid-pass"
        )
        assert fails == []

    def test_fail_case_returns_failures_but_does_not_raise(self):
        fails = _check_legal_current_before_save(
            "<p>구직급여 상한액은 66,000원입니다.</p>", "unemployment-benefit", "cid-fail"
        )
        assert fails
        assert fails[0]["gate"] == "G-LEGAL-CURRENT"

    def test_helper_never_raises_even_on_bad_input(self):
        # 논블로킹 원칙 확인: 어떤 입력에도 예외를 던지지 않아야 한다(저장 흐름을 막지 않기 위함).
        fails = _check_legal_current_before_save(None, "unemployment-benefit", "cid-none")
        assert isinstance(fails, list)


class TestExistingBehaviorUnchanged:
    """Test E: 정상 콘텐츠의 기존 저장 동작/구조가 이번 STEP으로 바뀌지 않아야 한다."""

    def test_writer_result_keys_backward_compatible(self):
        repo = FakeRepo()
        res = _run_writer("<p>정상 콘텐츠</p>", repo)
        # 기존에 있던 키들이 전부 유지되어야 한다.
        for key in ("seo_title", "seo_description", "faq", "article_content", "_saved"):
            assert key in res

    def test_content_ssot_coverage_added_for_step28_26_targets(self):
        """이번 STEP에서 추가한 content_ssot 커버리지가 실제로 반영되었는지 확인."""
        from modules.law_ssot import get_ssot_prompt_block

        assert "10,320원" in get_ssot_prompt_block("weekly-holiday-allowance")
        assert "66,048원" in get_ssot_prompt_block("unemployment-benefit")
        assert "410,000원" in get_ssot_prompt_block("four-insurances")
        assert "6,590,000원" in get_ssot_prompt_block("four-insurances")
        assert "410,000원" in get_ssot_prompt_block("연말정산_환급액_계산기")
        assert "6,590,000원" in get_ssot_prompt_block("연말정산_환급액_계산기")

    def test_compute_logic_untouched(self):
        import modules.app_generator as AG

        js = AG._compute_js({"slug": "unemployment-benefit"})
        assert "68100" in js and "66048" in js
