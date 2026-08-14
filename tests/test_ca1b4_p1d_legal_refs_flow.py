# -*- coding: utf-8 -*-
"""tests/test_ca1b4_p1d_legal_refs_flow.py — CA-1B-4 P1-D

Registry legal_refs 전달 경로 복구 검증:
  Registry entry.legal_refs
    → prefill_contract_from_registry() 반환 (legal_refs 상위 필드)
    → build_contract() 전달 → Contract.legal_refs 보존
    → suggest_formula() legal_refs 인자 (Type D 차단 복구)
    → P1-B scope_exclusions TYPE A/B 분류 복구
    → HOLD-3 (confidence=medium) 감지 복구

※ Dashboard session_state(af_contract_legal_refs) 저장은 Streamlit 런타임
  (streamlit run) 없이는 검증 불가 — 실서버 Smoke Test에서 확인한다.
  본 파일은 그 데이터 흐름을 app_factory 레벨에서 검증한다.

운영 파일 수정 없음 — 실제 docs/registry·legal_master는 read-only로 읽기만.
실제 Contract instance 생성 없음.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import modules.app_factory as af
from modules.app_factory import (
    build_contract,
    check_hold_rules,
    prefill_contract_from_registry,
)

# 실데이터 상수 (P1-D 조사에서 확인 — docs/registry + docs/legal_master)
SEVERANCE_PAY_REF = "worker_retirement_benefit_act_8"
UNEMPLOYMENT_REF = "employment_insurance_act_40"   # confidence=medium
UNEMPLOYMENT_FP = ["받을 수 있습니다", "받게 됩니다", "수급 대상입니다"]


# ── Test 1/2/3: prefill 반환에 legal_refs ──────────────────────────────────
class TestPrefillReturnsLegalRefs:

    def test_prefill_includes_legal_refs_from_real_registry(self):
        """severance-pay (실제 Registry) → prefill 결과에 legal_refs 존재."""
        r = prefill_contract_from_registry("severance-pay")
        assert r["found"] is True
        assert r["legal_refs"] == [SEVERANCE_PAY_REF]

    def test_prefill_missing_legal_refs_returns_empty(self):
        """legal_refs 키가 없는 Registry 엔트리 → [] (추측 금지)."""
        reg = {"calc-a": {"name": "A", "input_labels": ["x"], "output_labels": ["y"]}}
        r = prefill_contract_from_registry("calc-a", registry=reg)
        assert r["found"] is True
        assert r["legal_refs"] == []

    def test_prefill_none_legal_refs_returns_empty(self):
        """legal_refs가 None인 Registry 엔트리 → []."""
        reg = {"calc-b": {"name": "B", "legal_refs": None,
                          "input_labels": ["x"], "output_labels": ["y"]}}
        r = prefill_contract_from_registry("calc-b", registry=reg)
        assert r["found"] is True
        assert r["legal_refs"] == []

    def test_prefill_missing_slug_returns_empty(self):
        """Registry에 없는 slug → found=False + legal_refs=[]."""
        r = prefill_contract_from_registry("no-such-calc-xyz")
        assert r["found"] is False
        assert r["legal_refs"] == []


# ── Test 5: build_contract 전달 (Registry → Contract 체인) ─────────────────
class TestBuildContractReceivesLegalRefs:

    def test_contract_legal_refs_from_prefill(self):
        """실제 prefill 결과의 legal_refs를 build_contract에 전달 → 보존."""
        pf = prefill_contract_from_registry("severance-pay")
        contract = build_contract(
            slug="severance-pay",
            name="퇴직금 계산기",
            category="노무/급여",
            tier="Tier2-A",
            input_fields=pf["input_fields"],
            output_fields=pf["output_fields"],
            scope_exclusions=pf["scope_exclusions"],
            legal_refs=pf["legal_refs"],
        )
        assert contract["legal_refs"] == [SEVERANCE_PAY_REF]

    def test_manual_contract_default_empty(self):
        """수동(프리필 미사용) Contract → legal_refs=[] 기본값, 예외 없음."""
        c = build_contract(slug="manual-calc", name="수동계산기",
                           input_fields=["a"], output_fields=["b"])
        assert c["legal_refs"] == []


# ── Test 6: suggest_formula legal_refs 전달 → Type D 차단 복구 ──────────────
class TestSuggestFormulaLegalRefs:

    def test_type_d_blocked_via_legal_refs(self, monkeypatch):
        """legal_refs=실업급여 → calculation_flow 조회 → 기존 Type D 차단 발동.
        (매년 변경/별표 키워드 — real legal_master, _chat 호출 없이 차단)"""
        calls = []

        def _noop_chat(*a, **k):
            calls.append(a)
            return ('{"formula": "x"}', "gpt", 1)

        monkeypatch.setattr(af, "_chat", _noop_chat)
        r = af.suggest_formula(
            cfg={"DB_ADAPTER": "memory"},
            name="실업급여 계산기",
            category="고용/보험",
            input_fields=["avg_daily_wage", "age", "employment_months"],
            output_fields=["daily_benefit", "total_benefit"],
            legal_refs=[UNEMPLOYMENT_REF],
        )
        assert r["success"] is False, "Type D 차단이 legal_refs로 발동해야 한다"
        assert calls == [], "Type D 차단은 _chat 호출 전에 이뤄져야 한다"

    def test_no_legal_refs_no_type_d_block(self, monkeypatch):
        """legal_refs=[] → calc_flows 미조회 → _chat 정상 호출 (Type D 아님)."""
        calls = []

        def _mock_chat(*a, **k):
            calls.append(a)
            return ('{"formula": "a + b", "labels": {}}', "gpt", 1)

        monkeypatch.setattr(af, "_chat", _mock_chat)
        r = af.suggest_formula(
            cfg={"DB_ADAPTER": "memory"},
            name="단순 계산기",
            input_fields=["a", "b"],
            output_fields=["c"],
            legal_refs=[],
        )
        assert r["success"] is True
        assert len(calls) == 1, "legal_refs가 없으면 AI 제안 경로가 유지되어야 한다"


# ── Test 7: P1-B TYPE A 분류 복구 (Registry prefill 기반) ──────────────────
class TestP1BClassificationWithRealLegalRefs:

    def test_type_a_article_classified_from_prefill_chain(self):
        """severance-pay 프리필 → Contract → _scope_exclusions_by_type()
        → 근로기준법 제34조가 [인용 금지 조항]으로 분류된다 (legal_refs 연동)."""
        pf = prefill_contract_from_registry("severance-pay")
        contract = build_contract(
            slug="severance-pay",
            name="퇴직금 계산기",
            category="노무/급여",
            tier="Tier2-A",
            input_fields=pf["input_fields"],
            output_fields=pf["output_fields"],
            scope_exclusions=pf["scope_exclusions"],
            legal_refs=pf["legal_refs"],
        )
        type_a, type_b, other = af._scope_exclusions_by_type(
            contract["scope_exclusions"], contract["legal_refs"])
        assert "근로기준법 제34조" in type_a
        assert "근로기준법 제34조" not in other, \
            "legal_refs 연동 시 TYPE A 분류가 되어야 한다 (기타로 떨어지면 안 됨)"

    def test_type_b_phrases_classified_from_prefill_chain(self):
        """unemployment-benefit 프리필 → 금지 표현 3개가 TYPE B로 분류."""
        pf = prefill_contract_from_registry("unemployment-benefit")
        contract = build_contract(
            slug="unemployment-benefit",
            name="실업급여 계산기",
            category="고용/보험",
            tier="Tier2-A",
            input_fields=pf["input_fields"],
            output_fields=pf["output_fields"],
            scope_exclusions=pf["scope_exclusions"],
            legal_refs=pf["legal_refs"],
        )
        type_a, type_b, other = af._scope_exclusions_by_type(
            contract["scope_exclusions"], contract["legal_refs"])
        assert set(UNEMPLOYMENT_FP) <= set(type_b), \
            f"금지 표현이 TYPE B로 분류되어야 한다: {type_b}"


# ── Test 8: HOLD-3 감지 복구 ────────────────────────────────────────────────
class TestHold3WithRealLegalRefs:

    def test_hold3_fires_for_medium_confidence_ref(self):
        """legal_refs=employment_insurance_act_40(confidence=medium) → HOLD-3."""
        contract = build_contract(
            slug="unemployment-benefit",
            name="실업급여 계산기",
            category="고용/보험",
            tier="Tier2-A",
            input_fields=["avg_daily_wage", "age", "employment_months"],
            output_fields=["daily_benefit", "total_benefit"],
            legal_refs=[UNEMPLOYMENT_REF],
        )
        hold = check_hold_rules(contract)
        assert "HOLD-3" in hold["rules"]
        assert any("HOLD-3" in m for m in hold["messages"])

    def test_hold3_not_fires_for_high_confidence_ref(self):
        """legal_refs=worker_retirement_benefit_act_8(confidence=high) → HOLD-3 없음."""
        contract = build_contract(
            slug="severance-pay",
            name="퇴직금 계산기",
            category="노무/급여",
            tier="Tier2-A",
            input_fields=["avg_monthly_wage", "total_days"],
            output_fields=["severance_pay"],
            legal_refs=[SEVERANCE_PAY_REF],
        )
        hold = check_hold_rules(contract)
        assert "HOLD-3" not in hold["rules"]


# ── Test 9: Mode A 보호 (legal_refs 없음 → 기존 동작) ───────────────────────
class TestModeAProtection:

    def test_no_contract_no_legal_refs_flow(self):
        """프리필 없는 수동 Contract는 legal_refs=[]로 안전하게 생성."""
        c = build_contract(slug="mode-a-calc", name="ModeA",
                           input_fields=["a"], output_fields=["b"])
        assert c["legal_refs"] == []
        assert "legal_refs" in c  # key 자체는 항상 존재

    def test_checklist_path_unchanged_for_empty_legal_refs(self):
        """legal_refs=[]여도 review_center extract_checklist가 예외 없이 동작."""
        from modules.review_center import extract_checklist
        app = {
            "name": "A", "category": "세금/세법", "formula": "a * 0.1",
            "legal_refs": [], "input_schema": {"a": "number"},
            "output_schema": {"b": "number"}, "compute_type": "formula",
            "tier": 2,
        }
        items = extract_checklist(app, tier="Tier2-A", category="세금/세법")
        assert any(i["id"] == "legal_basis" for i in items)


# ── Test 10: 기존 lifecycle 보호 (legal_refs 보존 + P1-C gate) ─────────────
class TestLifecycleProtection:

    def test_generate_app_with_contract_preserves_legal_refs(self, monkeypatch):
        """generate_app_with_contract(mock _chat) → 결과 _contract에 legal_refs 보존."""
        from tests.test_ca1b4_p1b_scope_exclusions_prompt import _capture_chat
        contract = build_contract(
            slug="severance-pay",
            name="퇴직금 계산기",
            category="노무/급여",
            tier="Tier2-A",
            input_fields=["avg_monthly_wage", "total_days"],
            output_fields=["severance_pay"],
            scope_exclusions=["근로기준법 제34조"],
            legal_refs=[SEVERANCE_PAY_REF],
            formula="avg_monthly_wage * (total_days / 365) * 30",
        )
        calls = []
        monkeypatch.setattr(af, "_chat", _capture_chat(calls))
        result = af.generate_app_with_contract({"DB_ADAPTER": "memory"}, contract)
        assert result["_contract"]["legal_refs"] == [SEVERANCE_PAY_REF]
        assert result["_contract"]["scope_exclusions"] == ["근로기준법 제34조"]
        # enforcement prompt에 legal_refs 기반 TYPE A 분류가 반영된다
        joined = "\n".join(c["system"] for c in calls)
        assert "근로기준법 제34조" in joined
        assert "[인용 금지 조항]" in joined

    def test_p1c_save_gate_unchanged_with_legal_refs(self, monkeypatch):
        """legal_refs 포함 Contract도 P1-C Hard-Gate 동작 유지 (operator_confirmed만 허용)."""
        from tests.test_ca1b4_p1c_hold_save_gate import (
            _app as _p1c_app,
            _contract as _p1c_contract,
            _patch_side_effects as _p1c_patch,
        )
        _p1c_patch(monkeypatch)
        contract = _p1c_contract("pending_validation")
        contract["legal_refs"] = [SEVERANCE_PAY_REF]
        app = _p1c_app(contract)
        ok, msg = af.save_app({"DB_ADAPTER": "memory"}, app, slug="test-calc")
        assert ok is False
        assert "operator_confirmed" in msg or "확정" in msg
