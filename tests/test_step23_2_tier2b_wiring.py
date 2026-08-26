# -*- coding: utf-8 -*-
"""tests/test_step23_2_tier2b_wiring.py — STEP 23-2 회귀 테스트

STEP 23-1에서 발견된 결함: review_center.suggest_tier()가 "Tier2-B"를 반환해도
dashboard.py의 _tier_map_str_to_int()에서 Tier2-A/B가 동일한 정수 2로 축약되어,
Mode B의 _af_is_tier2b 체크박스로 전달되지 않았다.

STEP 23-2 수정: AI 추천 버튼 핸들러에서 confidence와 무관하게
"tier == 'Tier2-B'" 여부만 session_state(af_tier2b_suggested, af_contract_is_tier2b)에
보존하여 체크박스 기본값까지 배선한다. Mode A는 subtype 개념이 없으므로 무변경.

기존 tests/test_af_contract_dashboard.py의 관례를 따라, dashboard.py의 UI 로직은
Streamlit 없이 소스 검사(inspect.getsource) + 동일 로직을 순수 함수로 재현해 검증한다.
"""
import inspect
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from modules import review_center as RC

_DASHBOARD_SRC = (Path(__file__).resolve().parent.parent / "dashboard.py").read_text(encoding="utf-8")


# ── dashboard.py 로직 재현 (UI 없이 순수 함수로) ──────────────────────────────

def _tier2b_suggested_from(result: dict) -> bool:
    """dashboard.py AI 추천 핸들러의 신규 배선 로직 재현."""
    return result.get("tier") == "Tier2-B"


def _mode_b_contract_tier(af_tier: int, is_tier2b_checked: bool) -> str:
    """dashboard.py:~2502 Mode B 저장 시 contract['tier'] 결정 로직 재현."""
    _tier_map_int_to_str = {2: "Tier2-A", 1: "Tier1"}
    return "Tier2-B" if is_tier2b_checked else _tier_map_int_to_str.get(af_tier, "Tier2-A")


# ── Test 1~6: suggest_tier() 반환값 → subtype 신호가 confidence와 무관하게 보존 ──

class TestTier2BSuggestionSignal:
    """confidence(high/medium/low)와 무관하게 tier=='Tier2-B'일 때만 True."""

    def _mock_chat(self, tier: str, confidence: str):
        import json
        return (json.dumps({"tier": tier, "reason": "테스트", "confidence": confidence}), 0, 0)

    def test_1_tier2b_high_confidence(self):
        with patch("modules.app_factory._chat", return_value=self._mock_chat("Tier2-B", "high")):
            result = RC.suggest_tier({}, "군인 전역일 계산기", "입대일로 전역일 계산")
        assert result["tier"] == "Tier2-B"
        assert _tier2b_suggested_from(result) is True

    def test_2_tier2a_high_confidence_is_false(self):
        with patch("modules.app_factory._chat", return_value=self._mock_chat("Tier2-A", "high")):
            result = RC.suggest_tier({}, "BMI 계산기", "키/몸무게로 BMI 계산")
        assert _tier2b_suggested_from(result) is False

    def test_3_tier1_high_confidence_is_false(self):
        with patch("modules.app_factory._chat", return_value=self._mock_chat("Tier1", "high")):
            result = RC.suggest_tier({}, "퇴직금 계산기", "평균임금 기반 퇴직금")
        assert _tier2b_suggested_from(result) is False

    def test_4_tier2b_medium_confidence_still_true(self):
        with patch("modules.app_factory._chat", return_value=self._mock_chat("Tier2-B", "medium")):
            result = RC.suggest_tier({}, "날짜 계산기", "")
        assert _tier2b_suggested_from(result) is True

    def test_5_tier2b_low_confidence_still_true(self):
        """핵심: confidence가 낮아도 '추천 결과 자체'는 소실되면 안 된다(자동확정과는 별개)."""
        with patch("modules.app_factory._chat", return_value=self._mock_chat("Tier2-B", "low")):
            result = RC.suggest_tier({}, "애매한 날짜 계산기", "")
        assert _tier2b_suggested_from(result) is True

    def test_6_tier2a_low_confidence_is_false(self):
        with patch("modules.app_factory._chat", return_value=self._mock_chat("Tier2-A", "low")):
            result = RC.suggest_tier({}, "애매한 산술 계산기", "")
        assert _tier2b_suggested_from(result) is False


# ── Test 7: AI 실패 fallback ──────────────────────────────────────────────

class TestAIFailureFallback:
    def test_7_ai_failure_fallback_subtype_false(self):
        with patch("modules.app_factory._chat", side_effect=RuntimeError("API down")):
            result = RC.suggest_tier({}, "아무 계산기", "")
        assert result["tier"] == "Tier2-A"
        assert result["confidence"] == "low"
        assert _tier2b_suggested_from(result) is False


# ── Test 8: 사용자 override 보존 (소스 구조 검증) ─────────────────────────

class TestUserOverridePreserved:
    def test_8_session_state_write_only_inside_button_handler(self):
        """af_contract_is_tier2b에 대한 session_state 쓰기가
        '💡 Tier AI 추천' 버튼의 if 블록 내부에만 존재해야 한다.
        매 rerun마다 무조건 덮어쓰면 사용자가 체크박스를 수동으로 바꿔도
        되돌아가므로(override 불가) 버그가 된다."""
        btn_idx = _DASHBOARD_SRC.find('st.button("💡 Tier AI 추천"')
        assert btn_idx != -1, "AI 추천 버튼 코드를 찾을 수 없음"
        checkbox_idx = _DASHBOARD_SRC.find('key="af_contract_is_tier2b"')
        assert checkbox_idx != -1, "Tier2-B 체크박스 위젯을 찾을 수 없음"

        write_idx = _DASHBOARD_SRC.find('st.session_state["af_contract_is_tier2b"] =')
        assert write_idx != -1, "af_contract_is_tier2b session_state 쓰기가 없음(배선 누락)"
        # 쓰기 위치가 버튼 블록 시작과 체크박스 위젯 정의 사이에 있어야
        # "버튼 클릭 시에만 쓰고, 위젯 자체는 그 값을 읽기만 한다"는 구조가 보장된다.
        assert btn_idx < write_idx < checkbox_idx, (
            "af_contract_is_tier2b 쓰기 위치가 버튼 핸들러 내부(체크박스 위젯 정의 이전)에 있지 않음"
        )
        # 체크박스 위젯 자체에는 value= 강제 파라미터가 없어야 사용자 상호작용이
        # session_state를 자연스럽게 갱신할 수 있다(Streamlit 표준 위젯 동작).
        checkbox_block = _DASHBOARD_SRC[checkbox_idx - 200:checkbox_idx + 200]
        assert "value=" not in checkbox_block.split("st.checkbox(")[-1].split(")")[0], (
            "체크박스에 value=가 하드코딩되어 있으면 사용자가 매 rerun마다 override할 수 없음"
        )


# ── Test 9~11: Mode B tier/tier_subtype 조합 ──────────────────────────────

class TestModeBTierSubtypeCombination:
    def test_9_tier2b_checked_yields_tier2b(self):
        assert _mode_b_contract_tier(af_tier=2, is_tier2b_checked=True) == "Tier2-B"

    def test_10_tier2a_unchecked_yields_tier2a(self):
        assert _mode_b_contract_tier(af_tier=2, is_tier2b_checked=False) == "Tier2-A"

    def test_11_tier1_unchecked_yields_tier1(self):
        assert _mode_b_contract_tier(af_tier=1, is_tier2b_checked=False) == "Tier1"


# ── Test 12: Mode A 무영향 (소스 구조 검증) ───────────────────────────────

class TestModeAUnaffected:
    def test_12_mode_a_generate_app_call_has_no_subtype_reference(self):
        """Mode A(🏭 자동 생성) 버튼의 generate_app() 호출부는
        _af_is_tier2b/af_tier2b_suggested를 참조하면 안 된다(Mode A는 subtype 개념이 없음)."""
        mode_a_idx = _DASHBOARD_SRC.find("# ── Mode A: 자동 생성")
        mode_b_idx = _DASHBOARD_SRC.find("# ── Mode B: Contract 기반 생성")
        assert mode_a_idx != -1 and mode_b_idx != -1
        mode_a_block = _DASHBOARD_SRC[mode_a_idx:mode_b_idx]
        assert "_af_is_tier2b" not in mode_a_block
        assert "af_tier2b_suggested" not in mode_a_block
        assert "generate_app(" in mode_a_block
        assert "generate_app_with_contract" not in mode_a_block

    def test_12b_generate_app_signature_unchanged(self):
        """generate_app() 시그니처가 이번 변경으로 바뀌지 않았는지 확인."""
        import modules.app_factory as af_mod
        sig = str(inspect.signature(af_mod.generate_app))
        assert "tier" in sig
        assert "subtype" not in sig.lower()
