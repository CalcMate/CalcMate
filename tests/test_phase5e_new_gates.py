# -*- coding: utf-8 -*-
"""
Phase 5-E 신규 Gate 단위 테스트
G-LEGAL-CURRENT / G-CONSISTENCY / G-H2

절대 건드리지 않는 것: 기존 37개 production 콘텐츠, production pipeline.
"""
import pytest
from modules.content_integrity import (
    check_g_legal_current,
    check_g_consistency,
    check_g_h2_structure,
    run_integrity_gates,
)


def _gate_names(failed: list) -> set:
    return {f["gate"] for f in failed}


def _grades(failed: list, gate: str) -> set:
    return {f["grade"] for f in failed if f["gate"] == gate}


# ═══════════════════════════════════════════════════════════════════════════
# G-LEGAL-CURRENT
# ═══════════════════════════════════════════════════════════════════════════

class TestGLegalCurrent:

    def test_outdated_health_rate_fails(self):
        """4대보험 글에서 구 요율 '3.52%' 등장 → CRITICAL fail."""
        body = "<p>건강보험료는 3.52%입니다.</p>"
        fails = check_g_legal_current(body, "four-insurances")
        assert "G-LEGAL-CURRENT" in _gate_names(fails)
        assert _grades(fails, "G-LEGAL-CURRENT") == {"critical"}

    def test_outdated_health_rate_535_fails(self):
        """3.535% (또 다른 구 요율) 탐지."""
        body = "<p>건강보험 3.535%가 부과됩니다.</p>"
        fails = check_g_legal_current(body, "four-insurances")
        assert "G-LEGAL-CURRENT" in _gate_names(fails)

    def test_outdated_ltc_rate_fails(self):
        """구 장기요양보험료율 '12.95%' 탐지."""
        body = "<p>장기요양보험료는 건보료의 12.95%입니다.</p>"
        fails = check_g_legal_current(body, "four-insurances")
        assert "G-LEGAL-CURRENT" in _gate_names(fails)

    def test_outdated_health_rate_545_fails(self):
        """3.545% (2025년 구 요율) → FAIL (2026년 갱신 후 금지값)."""
        body = "<p>건강보험료는 3.545%입니다.</p>"
        fails = check_g_legal_current(body, "four-insurances")
        assert "G-LEGAL-CURRENT" in _gate_names(fails)
        assert _grades(fails, "G-LEGAL-CURRENT") == {"critical"}

    def test_outdated_np_rate_45_fails(self):
        """4.5% (2025년 국민연금 구 요율) → FAIL."""
        body = "<p>국민연금은 월급여의 4.5%입니다.</p>"
        fails = check_g_legal_current(body, "four-insurances")
        assert "G-LEGAL-CURRENT" in _gate_names(fails)

    def test_correct_health_rate_passes(self):
        """현행 요율 3.595% 사용 → PASS (블랙리스트 기준)."""
        body = "<p>건강보험료는 3.595%입니다.</p>"
        fails = check_g_legal_current(body, "four-insurances")
        assert "G-LEGAL-CURRENT" not in _gate_names(fails)

    def test_wrong_deadline_7days_fails(self):
        """4대보험 취득신고 '7일 이내' → FAIL (현행: 14일 이내)."""
        body = "<p>취득신고는 7일 이내에 해야 합니다.</p>"
        fails = check_g_legal_current(body, "four-insurances")
        assert "G-LEGAL-CURRENT" in _gate_names(fails)

    def test_correct_deadline_14days_passes(self):
        """취득신고 '14일 이내' → PASS."""
        body = "<p>취득신고는 취득일로부터 14일 이내에 해야 합니다.</p>"
        fails = check_g_legal_current(body, "four-insurances")
        assert "G-LEGAL-CURRENT" not in _gate_names(fails)

    def test_parental_leave_old_cap_fails(self):
        """육아휴직 글에서 '상한 150만원' → FAIL (writer_note: 금액 미언급 원칙)."""
        body = "<p>육아휴직 급여 상한 150만원을 지급받습니다.</p>"
        fails = check_g_legal_current(body, "육아휴직_급여_계산기")
        assert "G-LEGAL-CURRENT" in _gate_names(fails)

    def test_parental_leave_old_120_cap_fails(self):
        """구 상한 '120만원'도 탐지."""
        body = "<p>이후 상한 120만원이 적용됩니다.</p>"
        fails = check_g_legal_current(body, "육아휴직_급여_계산기")
        assert "G-LEGAL-CURRENT" in _gate_names(fails)

    def test_parental_leave_no_cap_passes(self):
        """금액 미언급 + 고용노동부 안내 권유 → PASS."""
        body = "<p>육아휴직 급여는 고용노동부 최신 안내를 참고하세요.</p>"
        fails = check_g_legal_current(body, "육아휴직_급여_계산기")
        assert "G-LEGAL-CURRENT" not in _gate_names(fails)

    def test_unknown_slug_no_fail(self):
        """SSOT 없는 slug → 규칙 없음 → PASS."""
        body = "<p>임의의 내용입니다. 3.52% 등장해도 무관한 slug.</p>"
        fails = check_g_legal_current(body, "unknown-calc")
        assert "G-LEGAL-CURRENT" not in _gate_names(fails)

    def test_none_slug_no_fail(self):
        """slug=None → PASS (slug 불명 시 skip)."""
        body = "<p>3.52% 등장해도 slug가 없으면 무시.</p>"
        fails = check_g_legal_current(body, None)
        assert "G-LEGAL-CURRENT" not in _gate_names(fails)

    def test_blacklist_bypass_different_slug(self):
        """다른 slug에서 '7일 이내' 등장해도 four-insurances 전용 규칙은 미적용."""
        body = "<p>계약서 검토는 7일 이내에 완료하세요.</p>"
        fails = check_g_legal_current(body, "severance-pay")
        assert "G-LEGAL-CURRENT" not in _gate_names(fails)

    def test_detail_includes_current_value(self):
        """fail detail에 현행 값(3.595%)이 포함되어야 함."""
        body = "<p>건강보험료 3.52%.</p>"
        fails = check_g_legal_current(body, "four-insurances")
        details = [f["detail"] for f in fails if f["gate"] == "G-LEGAL-CURRENT"]
        assert any("3.595%" in d for d in details)

    def test_positive_check_current_rates_present_passes(self):
        """긍정검증: 3.595% + 4.75% 모두 포함 + calculator intent → PASS."""
        body = "<p>건강보험 3.595%, 국민연금 4.75% 적용.</p>"
        fails = check_g_legal_current(body, "four-insurances", intent="calculator")
        assert "G-LEGAL-CURRENT" not in _gate_names(fails)

    def test_positive_check_missing_health_rate_fails(self):
        """긍정검증: 3.595% 미등장 + calculator intent → FAIL (major)."""
        body = "<p>국민연금 4.75% 적용. 건강보험은 일정 비율입니다.</p>"
        fails = check_g_legal_current(body, "four-insurances", intent="calculator")
        assert "G-LEGAL-CURRENT" in _gate_names(fails)
        assert "major" in _grades(fails, "G-LEGAL-CURRENT")

    def test_positive_check_noncalculator_intent_passes(self):
        """긍정검증: eligibility intent → requires_in_content 미적용 → PASS."""
        body = "<p>4대보험 가입 조건 안내. 비율 미언급.</p>"
        fails = check_g_legal_current(body, "four-insurances", intent="eligibility")
        assert "G-LEGAL-CURRENT" not in _gate_names(fails)

    def test_positive_check_no_intent_passes(self):
        """긍정검증: intent=None → 긍정검증 비적용 → PASS."""
        body = "<p>4대보험 일반 설명. 비율 미언급.</p>"
        fails = check_g_legal_current(body, "four-insurances", intent=None)
        assert "G-LEGAL-CURRENT" not in _gate_names(fails)


# ═══════════════════════════════════════════════════════════════════════════
# G-CONSISTENCY
# ═══════════════════════════════════════════════════════════════════════════

class TestGConsistency:

    def test_consistent_rates_passes(self):
        """본문·FAQ 모두 3.595% → PASS."""
        body = (
            "<h2>계산 원리</h2><p>건강보험 3.595% 적용.</p>"
            "<h2>FAQ</h2><dl><dt>건보료율?</dt><dd>건강보험료는 3.595%입니다.</dd></dl>"
        )
        fails = check_g_consistency(body)
        assert "G-CONSISTENCY" not in _gate_names(fails)

    def test_inconsistent_rates_fails(self):
        """본문 3.595%, FAQ 3.52% → 불일치 → FAIL."""
        body = (
            "<h2>계산 원리</h2><p>건강보험 3.595% 적용.</p>"
            "<h2>FAQ</h2><dl><dt>건보료율?</dt><dd>건강보험료는 3.52%입니다.</dd></dl>"
        )
        fails = check_g_consistency(body)
        assert "G-CONSISTENCY" in _gate_names(fails)
        assert _grades(fails, "G-CONSISTENCY") == {"major"}

    def test_no_faq_section_passes(self):
        """FAQ 섹션 없는 본문 → G-CONSISTENCY 면제."""
        body = "<h2>계산 원리</h2><p>건강보험 3.595% 적용.</p>"
        fails = check_g_consistency(body)
        assert "G-CONSISTENCY" not in _gate_names(fails)

    def test_faq_only_rate_no_body_rates_passes(self):
        """본문에 rate 없고 FAQ에만 있어도 body_rates가 empty면 PASS (비교 불가)."""
        body = (
            "<h2>소개</h2><p>일반 설명.</p>"
            "<h2>FAQ</h2><dl><dt>질문?</dt><dd>3.595%입니다.</dd></dl>"
        )
        fails = check_g_consistency(body)
        assert "G-CONSISTENCY" not in _gate_names(fails)

    def test_out_of_range_rate_ignored(self):
        """범위 밖 퍼센트(예: 80% 육아휴직 급여율)는 비교 대상 제외."""
        body = (
            "<h2>지급 조건</h2><p>통상임금의 80%를 지급합니다. 건보료 3.595%.</p>"
            "<h2>FAQ</h2><dl><dt>급여율?</dt><dd>통상임금의 80%. 건보료 3.595%.</dd></dl>"
        )
        fails = check_g_consistency(body)
        assert "G-CONSISTENCY" not in _gate_names(fails)

    def test_detail_includes_faq_and_body_rates(self):
        """fail detail에 FAQ 수치와 본문 수치가 모두 포함."""
        body = (
            "<h2>계산 원리</h2><p>건강보험 3.595% 적용.</p>"
            "<h2>FAQ</h2><dl><dt>?</dt><dd>3.52%입니다.</dd></dl>"
        )
        fails = check_g_consistency(body)
        details = [f["detail"] for f in fails if f["gate"] == "G-CONSISTENCY"]
        assert any("3.52%" in d for d in details)
        assert any("3.595%" in d for d in details)

    # ── 기간(N일 이내) 불일치 ──────────────────────────────────────────────────

    def test_period_inconsistency_fails(self):
        """본문 '14일 이내', FAQ '7일 이내' → 법정기간 불일치 → FAIL."""
        body = (
            "<h2>지급 조건</h2><p>취득신고는 14일 이내에 해야 합니다.</p>"
            "<h2>FAQ</h2><dl><dt>신고기한?</dt><dd>취득신고는 7일 이내입니다.</dd></dl>"
        )
        fails = check_g_consistency(body)
        assert "G-CONSISTENCY" in _gate_names(fails)
        details = [f["detail"] for f in fails if f["gate"] == "G-CONSISTENCY"]
        assert any("7일" in d for d in details)

    def test_period_consistent_passes(self):
        """본문·FAQ 모두 '14일 이내' → PASS."""
        body = (
            "<h2>지급 조건</h2><p>취득신고는 14일 이내.</p>"
            "<h2>FAQ</h2><dl><dt>기한?</dt><dd>14일 이내에 신고해야 합니다.</dd></dl>"
        )
        fails = check_g_consistency(body)
        assert "G-CONSISTENCY" not in _gate_names(fails)

    def test_period_faq_only_no_body_period_passes(self):
        """본문에 'N일 이내' 없고 FAQ에만 있어도 body_periods empty면 PASS."""
        body = (
            "<h2>소개</h2><p>일반 안내.</p>"
            "<h2>FAQ</h2><dl><dt>기한?</dt><dd>14일 이내.</dd></dl>"
        )
        fails = check_g_consistency(body)
        assert "G-CONSISTENCY" not in _gate_names(fails)

    # ── 법정 상한/하한 금액 불일치 ───────────────────────────────────────────────

    def test_ceiling_inconsistency_fails(self):
        """본문 '상한 68,100원', FAQ '상한 66,000원' → 법정금액 불일치 → FAIL."""
        body = (
            "<h2>지급 조건</h2><p>구직급여 1일 상한 68,100원이 적용됩니다.</p>"
            "<h2>FAQ</h2><dl><dt>상한?</dt><dd>구직급여 상한 66,000원입니다.</dd></dl>"
        )
        fails = check_g_consistency(body)
        assert "G-CONSISTENCY" in _gate_names(fails)

    def test_ceiling_consistent_passes(self):
        """본문·FAQ 모두 '상한 68,100원' → PASS."""
        body = (
            "<h2>지급 조건</h2><p>구직급여 1일 상한 68,100원.</p>"
            "<h2>FAQ</h2><dl><dt>상한?</dt><dd>상한 68,100원입니다.</dd></dl>"
        )
        fails = check_g_consistency(body)
        assert "G-CONSISTENCY" not in _gate_names(fails)

    def test_arithmetic_amount_no_false_positive(self):
        """산술 결과 금액('200만원 × 80% = 160만원')은 상한/하한 패턴 아님 → PASS."""
        body = (
            "<h2>지급 조건</h2><p>통상임금 200만원 × 80% = 160만원 예시.</p>"
            "<h2>FAQ</h2><dl><dt>예시?</dt><dd>150만원 × 80% = 120만원.</dd></dl>"
        )
        fails = check_g_consistency(body)
        assert "G-CONSISTENCY" not in _gate_names(fails)


# ═══════════════════════════════════════════════════════════════════════════
# G-H2
# ═══════════════════════════════════════════════════════════════════════════

class TestGH2Structure:

    def test_eligibility_all_required_passes(self):
        """eligibility 필수 H2 모두 존재 → PASS."""
        body = (
            "<h2>지급 대상</h2><p>내용.</p>"
            "<h2>근로시간 조건</h2><p>내용.</p>"
            "<h2>제외 대상</h2><p>내용.</p>"
            "<h2>계산 방법</h2><p>내용.</p>"
            "<h2>FAQ</h2><dl><dt>Q</dt><dd>A</dd></dl>"
        )
        fails = check_g_h2_structure(body, "eligibility")
        assert "G-H2" not in _gate_names(fails)

    def test_eligibility_missing_h2_fails(self):
        """eligibility에서 필수 H2 누락 → FAIL."""
        body = "<h2>지급 대상</h2><p>내용.</p><h2>FAQ</h2><p>내용.</p>"
        fails = check_g_h2_structure(body, "eligibility")
        assert "G-H2" in _gate_names(fails)

    def test_howto_required_passes(self):
        """howto 필수 H2 모두 존재 → PASS."""
        body = (
            "<h2>이용 절차</h2><p>내용.</p>"
            "<h2>계산 예시</h2><p>내용.</p>"
            "<h2>주의사항</h2><p>내용.</p>"
            "<h2>FAQ</h2><p>내용.</p>"
        )
        fails = check_g_h2_structure(body, "howto")
        assert "G-H2" not in _gate_names(fails)

    def test_howto_legacy_h2_fails(self):
        """'계산기 이용 방법' H2 탐지 (구 패턴)."""
        body = (
            "<h2>이용 절차</h2><p>내용.</p>"
            "<h2>계산 예시</h2><p>내용.</p>"
            "<h2>계산기 이용 방법</h2><p>구 패턴.</p>"
            "<h2>FAQ</h2><p>내용.</p>"
        )
        fails = check_g_h2_structure(body, "howto")
        assert "G-H2" in _gate_names(fails)
        details = [f["detail"] for f in fails if f["gate"] == "G-H2"]
        assert any("계산기 이용 방법" in d for d in details)

    def test_legacy_h2_calculator_intro_fails(self):
        """'계산기 소개' H2 탐지 (구 패턴)."""
        body = "<h2>계산기 소개</h2><p>설명.</p><h2>FAQ</h2><p>내용.</p>"
        fails = check_g_h2_structure(body, "calculator")
        assert "G-H2" in _gate_names(fails)

    def test_legacy_h2_input_method_fails(self):
        """'입력 방법' H2 탐지."""
        body = "<h2>입력 방법</h2><p>설명.</p>"
        fails = check_g_h2_structure(body, None)
        assert "G-H2" in _gate_names(fails)

    def test_documents_required_passes(self):
        """documents 필수 H2 모두 존재 → PASS."""
        body = (
            "<h2>필수 서류 목록</h2><p>내용.</p>"
            "<h2>서류 발급 방법</h2><p>내용.</p>"
            "<h2>제출 기한 및 절차</h2><p>내용.</p>"
            "<h2>주의사항</h2><p>내용.</p>"
            "<h2>FAQ</h2><p>내용.</p>"
        )
        fails = check_g_h2_structure(body, "documents")
        assert "G-H2" not in _gate_names(fails)

    def test_no_intent_only_legacy_check(self):
        """intent=None 이면 구 패턴만 검사."""
        body = "<h2>지급 대상</h2><p>내용.</p>"
        fails = check_g_h2_structure(body, None)
        assert "G-H2" not in _gate_names(fails)

    def test_no_intent_legacy_h2_still_detected(self):
        """intent=None 이어도 구 패턴은 탐지."""
        body = "<h2>결과 확인</h2><p>구 패턴.</p>"
        fails = check_g_h2_structure(body, None)
        assert "G-H2" in _gate_names(fails)


# ═══════════════════════════════════════════════════════════════════════════
# run_integrity_gates 통합 — 신규 Gate 포함
# ═══════════════════════════════════════════════════════════════════════════

class TestRunIntegrityGatesExtended:

    def test_new_gates_in_all_gates(self):
        """G-LEGAL-CURRENT / G-CONSISTENCY / G-H2 가 pass 목록에 포함."""
        body = (
            "<h2>지급 대상</h2><p>해당자.</p>"
            "<h2>제외 대상</h2><p>미해당자.</p>"
            "<h2>계산 방법</h2><p>총액은 600만원입니다.</p>"
            "<h2>FAQ</h2><dl><dt>Q</dt><dd>A</dd></dl>"
        )
        ctx = {"examples": [{"inputs": {}, "result": {"total": 6_000_000}}]}
        passed, _ = run_integrity_gates(body, slug="severance-pay", example_context=ctx, intent="eligibility")
        assert "G-LEGAL-CURRENT" in passed
        assert "G-CONSISTENCY" in passed
        assert "G-H2" in passed

    def test_outdated_rate_caught_in_integration(self):
        """통합 실행에서 G-LEGAL-CURRENT 탐지."""
        body = (
            "<h2>계산 원리</h2><p>건강보험 3.52% 부과됩니다.</p>"
            "<h2>지급 조건</h2><p>조건.</p>"
            "<h2>FAQ</h2><p>FAQ.</p>"
        )
        _, failed = run_integrity_gates(body, slug="four-insurances", intent="calculator")
        assert any(f["gate"] == "G-LEGAL-CURRENT" for f in failed)
        assert any(f["grade"] == "critical" for f in failed if f["gate"] == "G-LEGAL-CURRENT")

    def test_inconsistent_faq_body_caught_in_integration(self):
        """통합 실행에서 G-CONSISTENCY 탐지 (본문 3.595%, FAQ 3.52%)."""
        body = (
            "<h2>계산 원리</h2><p>건강보험 3.595% 부과됩니다.</p>"
            "<h2>지급 조건</h2><p>조건.</p>"
            "<h2>FAQ</h2><dl><dt>Q</dt><dd>건보료 3.52%.</dd></dl>"
        )
        _, failed = run_integrity_gates(body, slug="four-insurances", intent="calculator")
        assert any(f["gate"] == "G-CONSISTENCY" for f in failed)

    def test_legacy_h2_caught_in_integration(self):
        """통합 실행에서 G-H2 (구 패턴) 탐지."""
        body = (
            "<h2>계산기 소개</h2><p>설명.</p>"
            "<h2>계산 원리</h2><p>내용.</p>"
            "<h2>지급 조건</h2><p>조건.</p>"
            "<h2>FAQ</h2><p>FAQ.</p>"
        )
        _, failed = run_integrity_gates(body, slug="four-insurances", intent="calculator")
        assert any(f["gate"] == "G-H2" for f in failed)
