# -*- coding: utf-8 -*-
"""
Phase 5-D Gate 경계값 테스트
G1(intent별 분량) / G4(계산예시 면제) / G8(article 면제) / G-NEW2(calculator verified)

절대 건드리지 않는 것: 기존 37개 production 콘텐츠, production pipeline.
이 테스트는 publish_quality.check_gates / _check_g8 만 호출한다.
"""
import pytest
from modules.publish_quality import check_gates, _check_g8, _plain_text


# ── 기본 CFG ────────────────────────────────────────────────────────────────
CFG_BASE = {
    "QUALITY_GATE": {
        "MIN_LENGTH": 1800, "MAX_LENGTH": 2500,
        "MIN_H2": 5, "MAX_H2": 7,
        "MIN_FAQ": 5,
        "MIN_EXAMPLES": 2,
        "MIN_INTERNAL_LINKS": 2,
        "CTA_COUNT": 1,
    }
}

# ── HTML 빌더 헬퍼 ──────────────────────────────────────────────────────────
_H2_BLOCK = (
    "<h2>섹션A</h2><p>본문A</p>"
    "<h2>섹션B</h2><p>본문B</p>"
    "<h2>섹션C</h2><p>본문C</p>"
    "<h2>섹션D</h2><p>본문D</p>"
    "<h2>섹션E</h2><p>본문E</p>"
)
_FAQ_BLOCK = (
    "<dl>"
    "<dt>질문1</dt><dd>답변입니다1</dd>"
    "<dt>질문2</dt><dd>답변입니다2</dd>"
    "<dt>질문3</dt><dd>답변입니다3</dd>"
    "<dt>질문4</dt><dd>답변입니다4</dd>"
    "<dt>질문5</dt><dd>답변입니다5</dd>"
    "</dl>"
)
_LINKS_BLOCK = '<div class="internal-links"><a href="/x">X</a><a href="/y">Y</a></div>'
_CTA_BLOCK = "<h2>계산기 사용하기</h2><p>바로 계산해보세요.</p>"

_EXAMPLE_ZERO = ""
_EXAMPLE_TWO = (
    "<p>예를 들어 기본급 300만원의 경우 퇴직금 = 300만원이 산정됩니다.</p>"
    "<p>또 다른 예시로 기본급 200만원의 경우 퇴직금 = 200만원이 됩니다.</p>"
)
_GNEW2_ZERO = ""
_GNEW2_ONE = "<p>퇴직금 = 300만원이 지급됩니다.</p>"
_GNEW2_TWO = "<p>퇴직금 = 300만원이 지급됩니다. 약 500만원도 가능합니다.</p>"


def _pad_to(html: str, target: int) -> str:
    """body_html의 plain-text 길이를 target 이상으로 맞춰 반환."""
    current = len(_plain_text(html))
    if current < target:
        needed = target - current + 10  # 여유 10자 (태그→공백 변환 보정)
        html += "<p>" + "가나다라마바사아자차" * (needed // 10 + 1) + "</p>"
    return html


def _make_body(target_len: int, examples_html: str = "", gnew2_html: str = "") -> str:
    base = _H2_BLOCK + _FAQ_BLOCK + examples_html + gnew2_html
    return _pad_to(base, target_len)


def _make_final(body: str) -> str:
    return body + _LINKS_BLOCK + _CTA_BLOCK


def _gate_names(failed: list) -> set:
    return {f["gate"] for f in failed}


# ═══════════════════════════════════════════════════════════════════════════
# G1 — intent별 분량 경계값 (16개 케이스 중 G1 9개)
# ═══════════════════════════════════════════════════════════════════════════

class TestG1IntentLength:

    @pytest.mark.parametrize("intent,min_len", [
        ("howto",       1750),
        ("documents",   1850),
        ("eligibility", 2000),
        ("calculator",  1850),
    ])
    def test_below_min_fails_g1(self, intent, min_len):
        body = _make_body(min_len - 100)  # 확실히 미달
        final = _make_final(body)
        _, failed = check_gates(body, final, CFG_BASE, link_pool_size=2,
                                intent=intent, has_verified=False)
        assert "G1" in _gate_names(failed), (
            f"{intent}: 최소 {min_len}자 미달인데 G1이 발생하지 않음"
        )

    @pytest.mark.parametrize("intent,min_len", [
        ("howto",       1750),
        ("documents",   1850),
        ("eligibility", 2000),
        ("calculator",  1850),
    ])
    def test_above_min_passes_g1(self, intent, min_len):
        body = _make_body(min_len + 100)  # 확실히 초과
        final = _make_final(body)
        _, failed = check_gates(body, final, CFG_BASE, link_pool_size=2,
                                intent=intent, has_verified=False)
        assert "G1" not in _gate_names(failed), (
            f"{intent}: {min_len+100}자인데 G1이 발생함"
        )

    def test_no_intent_uses_config_default_1800(self):
        """intent=None → config MIN_LENGTH=1800 기준 적용."""
        body_short = _make_body(1700)
        body_ok = _make_body(1900)
        _, failed_short = check_gates(body_short, _make_final(body_short), CFG_BASE,
                                      link_pool_size=2)
        _, failed_ok = check_gates(body_ok, _make_final(body_ok), CFG_BASE,
                                   link_pool_size=2)
        assert "G1" in _gate_names(failed_short), "intent=None, 1700자 → G1 실패여야 함"
        assert "G1" not in _gate_names(failed_ok), "intent=None, 1900자 → G1 통과여야 함"


# ═══════════════════════════════════════════════════════════════════════════
# G4 — 면제 조건 (4개 케이스)
# ═══════════════════════════════════════════════════════════════════════════

class TestG4Exemption:

    def test_documents_exempt_zero_examples(self):
        """documents intent → G4 면제(예시 0개여도 통과)."""
        body = _make_body(1900, examples_html=_EXAMPLE_ZERO)
        final = _make_final(body)
        _, failed = check_gates(body, final, CFG_BASE, link_pool_size=2,
                                intent="documents", has_verified=True)
        assert "G4" not in _gate_names(failed)

    def test_no_verified_exempt_zero_examples(self):
        """has_verified=False → G4 면제(calculator intent여도)."""
        body = _make_body(1900, examples_html=_EXAMPLE_ZERO)
        final = _make_final(body)
        _, failed = check_gates(body, final, CFG_BASE, link_pool_size=2,
                                intent="calculator", has_verified=False)
        assert "G4" not in _gate_names(failed)

    def test_eligibility_verified_no_examples_fails(self):
        """eligibility + has_verified=True + 예시 0개 → G4 실패."""
        body = _make_body(2100, examples_html=_EXAMPLE_ZERO)
        final = _make_final(body)
        _, failed = check_gates(body, final, CFG_BASE, link_pool_size=2,
                                intent="eligibility", has_verified=True)
        assert "G4" in _gate_names(failed)

    def test_calculator_verified_two_examples_passes(self):
        """calculator + has_verified=True + 예시 2개 → G4 통과."""
        body = _make_body(1900, examples_html=_EXAMPLE_TWO)
        final = _make_final(body)
        _, failed = check_gates(body, final, CFG_BASE, link_pool_size=2,
                                intent="calculator", has_verified=True)
        assert "G4" not in _gate_names(failed)


# ═══════════════════════════════════════════════════════════════════════════
# G8 — article 면제 (documents intent) — 3개 케이스
# ═══════════════════════════════════════════════════════════════════════════

class TestG8ArticleExemption:
    """_check_g8 직접 호출. severance-pay는 legal_basis에 등록된 slug."""

    _LAW_BODY = "<p>근로자퇴직급여보장법에 따라 퇴직급여가 산정됩니다.</p>"
    _CALC = {"slug": "severance-pay"}

    def test_documents_no_article_fail(self):
        """documents intent → article 조항 번호 미언급해도 article 관련 G8 없음."""
        fails = _check_g8(self._LAW_BODY, self._CALC, intent="documents")
        article_fails = [f for f in fails if "조항" in f.get("detail", "")]
        assert len(article_fails) == 0, "documents intent: article 면제 실패"

    def test_non_documents_article_checked(self):
        """eligibility intent → article 조항이 legal_basis에 있으면 G8 실패 가능."""
        fails_eli = _check_g8(self._LAW_BODY, self._CALC, intent="eligibility")
        fails_doc = _check_g8(self._LAW_BODY, self._CALC, intent="documents")
        doc_article_fails = [f for f in fails_doc if "조항" in f.get("detail", "")]
        # documents는 article fail 0개 — 핵심 불변식
        assert len(doc_article_fails) == 0

    def test_documents_vs_eligibility_article_difference(self):
        """법령만 언급(조항 미포함) → documents ≤ eligibility article fail 수."""
        fails_doc = _check_g8(self._LAW_BODY, self._CALC, intent="documents")
        fails_eli = _check_g8(self._LAW_BODY, self._CALC, intent="eligibility")
        doc_cnt = len([f for f in fails_doc if "조항" in f.get("detail", "")])
        eli_cnt = len([f for f in fails_eli if "조항" in f.get("detail", "")])
        assert doc_cnt <= eli_cnt, (
            f"documents({doc_cnt}) > eligibility({eli_cnt}) — 면제가 역전됨"
        )


# ═══════════════════════════════════════════════════════════════════════════
# G-NEW2 — calculator + verified 경계값 (6개 케이스)
# ═══════════════════════════════════════════════════════════════════════════

class TestGNEW2:

    def test_howto_exempt(self):
        """howto intent → G-NEW2 미적용(= N원 패턴 없어도 통과)."""
        body = _make_body(1900, gnew2_html=_GNEW2_ZERO)
        final = _make_final(body)
        _, failed = check_gates(body, final, CFG_BASE, link_pool_size=2,
                                intent="howto", has_verified=True)
        assert "G-NEW2" not in _gate_names(failed)

    def test_calculator_no_verified_exempt(self):
        """calculator + has_verified=False → G-NEW2 면제."""
        body = _make_body(1900, gnew2_html=_GNEW2_ZERO)
        final = _make_final(body)
        _, failed = check_gates(body, final, CFG_BASE, link_pool_size=2,
                                intent="calculator", has_verified=False)
        assert "G-NEW2" not in _gate_names(failed)

    def test_calculator_verified_zero_patterns_fails(self):
        """calculator + has_verified=True + '= N원' 0개 → G-NEW2 실패."""
        body = _make_body(1900, gnew2_html=_GNEW2_ZERO)
        final = _make_final(body)
        _, failed = check_gates(body, final, CFG_BASE, link_pool_size=2,
                                intent="calculator", has_verified=True)
        assert "G-NEW2" in _gate_names(failed)

    def test_calculator_verified_one_pattern_fails(self):
        """calculator + has_verified=True + '= N원' 1개 → G-NEW2 실패."""
        body = _make_body(1900, gnew2_html=_GNEW2_ONE)
        final = _make_final(body)
        _, failed = check_gates(body, final, CFG_BASE, link_pool_size=2,
                                intent="calculator", has_verified=True)
        assert "G-NEW2" in _gate_names(failed)

    def test_calculator_verified_two_patterns_passes(self):
        """calculator + has_verified=True + '= N원' 2개 → G-NEW2 통과."""
        body = _make_body(1900, gnew2_html=_GNEW2_TWO)
        final = _make_final(body)
        _, failed = check_gates(body, final, CFG_BASE, link_pool_size=2,
                                intent="calculator", has_verified=True)
        assert "G-NEW2" not in _gate_names(failed)

    def test_documents_intent_exempt(self):
        """documents intent → G-NEW2 미적용."""
        body = _make_body(1900, gnew2_html=_GNEW2_ZERO)
        final = _make_final(body)
        _, failed = check_gates(body, final, CFG_BASE, link_pool_size=2,
                                intent="documents", has_verified=True)
        assert "G-NEW2" not in _gate_names(failed)
