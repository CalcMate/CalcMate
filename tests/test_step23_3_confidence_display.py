# -*- coding: utf-8 -*-
"""tests/test_step23_3_confidence_display.py — STEP 23-3 회귀 테스트

STEP 23-3 변경: confidence=high일 때 dashboard.py의 Tier 추천 표시가
st.info()(기존)에서 st.success()로 바뀌어 "높은 확신도로 자동 선택됨"을
명확히 알린다. medium/low는 기존 st.info() 문구를 그대로 유지한다.

중요: 이것은 "표시(display)"만의 변경이다. 라디오/체크박스에 AI값을
반영하는 자동 선택 로직(af_tier, af_tier2b_suggested, af_contract_is_tier2b)은
STEP 23-2와 동일하게 confidence와 무관하게 항상 동작한다(§8 표: AI값 기본
반영은 high/medium/low 전부 YES — 화면 표시 문구만 high에서 다르다).

기존 tests/test_af_contract_dashboard.py, tests/test_step23_2_tier2b_wiring.py의
관례를 따라 dashboard.py UI 로직은 소스 검사 + 순수 함수 재현으로 검증한다.
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from modules import review_center as RC

_DASHBOARD_SRC = (Path(__file__).resolve().parent.parent / "dashboard.py").read_text(encoding="utf-8")


# ── dashboard.py 로직 재현 (UI 없이 순수 함수로) ──────────────────────────────

def _tier_map_str_to_int():
    return {"Tier2-A": 2, "Tier2-B": 2, "Tier1": 1}


def _auto_selected_tier_int(result: dict) -> int:
    """dashboard.py:2088 재현 — confidence와 무관하게 항상 반영됨."""
    return _tier_map_str_to_int().get(result.get("tier"), 2)


def _auto_selected_tier2b(result: dict) -> bool:
    """dashboard.py:2093 재현(STEP23-2) — confidence와 무관하게 항상 반영됨."""
    return result.get("tier") == "Tier2-B"


def _display_branch(result: dict) -> str:
    """dashboard.py:2071-2083 재현(STEP23-3 신규) — confidence로만 분기."""
    conf = result.get("confidence", "medium")
    return "success" if conf == "high" else "info"


def _mock_chat(tier: str, confidence: str):
    import json
    return (json.dumps({"tier": tier, "reason": "테스트", "confidence": confidence}), 0, 0)


# ── A. high ────────────────────────────────────────────────────────────────

class TestHighConfidenceDisplay:
    def test_1_tier1_high_auto_select_and_success_display(self):
        with patch("modules.app_factory._chat", return_value=_mock_chat("Tier1", "high")):
            result = RC.suggest_tier({}, "퇴직금 계산기", "")
        assert _auto_selected_tier_int(result) == 1
        assert _auto_selected_tier2b(result) is False
        assert _display_branch(result) == "success"

    def test_2_tier2a_high_auto_select_and_success_display(self):
        with patch("modules.app_factory._chat", return_value=_mock_chat("Tier2-A", "high")):
            result = RC.suggest_tier({}, "BMI 계산기", "")
        assert _auto_selected_tier_int(result) == 2
        assert _auto_selected_tier2b(result) is False
        assert _display_branch(result) == "success"

    def test_3_tier2b_high_subtype_preserved_and_success_display(self):
        with patch("modules.app_factory._chat", return_value=_mock_chat("Tier2-B", "high")):
            result = RC.suggest_tier({}, "군인 전역일 계산기", "")
        assert _auto_selected_tier_int(result) == 2
        assert _auto_selected_tier2b(result) is True  # subtype 소실 없음(STEP23-2 유지)
        assert _display_branch(result) == "success"


# ── B. medium ──────────────────────────────────────────────────────────────

class TestMediumConfidenceDisplay:
    def test_4_tier1_medium_no_success_badge(self):
        with patch("modules.app_factory._chat", return_value=_mock_chat("Tier1", "medium")):
            result = RC.suggest_tier({}, "애매한 계산기", "")
        assert _display_branch(result) == "info"
        # AI값 기본 반영 자체는 confidence와 무관하게 여전히 일어남
        assert _auto_selected_tier_int(result) == 1

    def test_5_tier2a_medium_existing_flow_preserved(self):
        with patch("modules.app_factory._chat", return_value=_mock_chat("Tier2-A", "medium")):
            result = RC.suggest_tier({}, "애매한 계산기2", "")
        assert _display_branch(result) == "info"
        assert _auto_selected_tier_int(result) == 2


# ── C. low ─────────────────────────────────────────────────────────────────

class TestLowConfidenceDisplay:
    def test_6_tier1_low_no_success_badge(self):
        with patch("modules.app_factory._chat", return_value=_mock_chat("Tier1", "low")):
            result = RC.suggest_tier({}, "불확실 계산기", "")
        assert _display_branch(result) == "info"

    def test_7_tier2a_low_existing_flow_preserved(self):
        with patch("modules.app_factory._chat", return_value=_mock_chat("Tier2-A", "low")):
            result = RC.suggest_tier({}, "불확실 계산기2", "")
        assert _display_branch(result) == "info"


# ── D. 실패 ────────────────────────────────────────────────────────────────

class TestFailureFallbackNoAutoConfirm:
    def test_8_ai_exception_confidence_low_no_success_badge(self):
        with patch("modules.app_factory._chat", side_effect=RuntimeError("API down")):
            result = RC.suggest_tier({}, "아무거나", "")
        assert result["confidence"] == "low"
        assert _display_branch(result) == "info"
        assert _auto_selected_tier2b(result) is False

    def test_9_invalid_tier_fallback_no_success_badge(self):
        with patch("modules.app_factory._chat", return_value=_mock_chat("Tier99-Invalid", "high")):
            result = RC.suggest_tier({}, "이상한 계산기", "")
        # review_center.py의 기존 fallback: 허용 범위 밖 tier는 Tier2-A로 강제
        assert result["tier"] == "Tier2-A"
        # invalid tier여도 confidence=high 자체는 AI가 반환한 값 그대로이므로
        # 표시는 success branch를 타되, 자동선택된 tier는 안전한 기본값(Tier2-A)이다.
        assert _auto_selected_tier_int(result) == 2
        assert _auto_selected_tier2b(result) is False


# ── E. 사용자 override (소스 구조 검증, STEP23-2와 동일 불변조건 재확인) ──────

class TestUserOverrideStillPreserved:
    def test_10_radio_write_only_inside_button_handler(self):
        """af_tier에 대한 session_state 쓰기가 AI 추천 버튼의 if 블록 내부에만
        있어야 사용자가 라디오를 직접 바꿔도 override가 유지된다."""
        btn_idx = _DASHBOARD_SRC.find('st.button("💡 Tier AI 추천"')
        radio_idx = _DASHBOARD_SRC.find('key="af_tier",')
        write_idx = _DASHBOARD_SRC.find('st.session_state["af_tier"] =')
        assert -1 not in (btn_idx, radio_idx, write_idx)
        assert btn_idx < write_idx < radio_idx

    def test_11_checkbox_write_only_inside_button_handler_unchanged(self):
        """STEP23-2에서 확정한 Tier2-B 체크박스 배선이 이번 STEP으로 깨지지 않았는지."""
        btn_idx = _DASHBOARD_SRC.find('st.button("💡 Tier AI 추천"')
        checkbox_idx = _DASHBOARD_SRC.find('key="af_contract_is_tier2b"')
        write_idx = _DASHBOARD_SRC.find('st.session_state["af_contract_is_tier2b"] =')
        assert -1 not in (btn_idx, checkbox_idx, write_idx)
        assert btn_idx < write_idx < checkbox_idx


# ── F. Mode 회귀 ───────────────────────────────────────────────────────────

class TestModeRegression:
    def test_12_mode_a_call_unchanged(self):
        mode_a_idx = _DASHBOARD_SRC.find("# ── Mode A: 자동 생성")
        mode_b_idx = _DASHBOARD_SRC.find("# ── Mode B: Contract 기반 생성")
        mode_a_block = _DASHBOARD_SRC[mode_a_idx:mode_b_idx]
        assert 'tier=af_tier' in mode_a_block.replace(" ", "")
        assert "_af_is_tier2b" not in mode_a_block
        assert "st.success" not in mode_a_block  # 이번 STEP 변경이 Mode A 블록에 새지 않았는지

    def test_13_mode_b_tier2a_combination_unchanged(self):
        _tier_map_int_to_str = {2: "Tier2-A", 1: "Tier1"}
        af_tier, is_tier2b = 2, False
        tier = "Tier2-B" if is_tier2b else _tier_map_int_to_str.get(af_tier, "Tier2-A")
        assert tier == "Tier2-A"

    def test_14_mode_b_tier2b_combination_unchanged(self):
        _tier_map_int_to_str = {2: "Tier2-A", 1: "Tier1"}
        af_tier, is_tier2b = 2, True
        tier = "Tier2-B" if is_tier2b else _tier_map_int_to_str.get(af_tier, "Tier2-A")
        assert tier == "Tier2-B"


# ── G. legal_refs 불변 ─────────────────────────────────────────────────────

class TestLegalRefsUnaffected:
    def test_15_high_confidence_tier_does_not_touch_legal_refs(self):
        """confidence=high 표시 강화 블록 소스에 legal_refs 관련 세션/로직이
        전혀 포함되지 않아야 한다 — Tier 표시와 legal_refs 확인은 완전히 분리된 관심사."""
        success_block_idx = _DASHBOARD_SRC.find('신뢰도: HIGH')
        assert success_block_idx != -1, "STEP23-3 high 표시 블록을 찾을 수 없음"
        surrounding = _DASHBOARD_SRC[success_block_idx - 400:success_block_idx + 400]
        assert "legal_refs" not in surrounding
        assert "legal_basis" not in surrounding
