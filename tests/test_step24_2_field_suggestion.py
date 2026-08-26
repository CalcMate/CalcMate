# -*- coding: utf-8 -*-
"""tests/test_step24_2_field_suggestion.py — STEP 24-2 회귀 테스트

STEP 24-2 변경: dashboard.py의 Mode B Contract 섹션에 "💡 필드 자동 제안" 버튼을
추가했다. 클릭 시 STEP 24-1의 modules.app_factory._suggest_spec()을 그대로
재사용해(신규 AI 프롬프트/로직 없음) input_schema/output_schema의 key를
af_contract_input_fields/af_contract_output_fields에, formula가 있으면
af_contract_formula에 프리필한다.

기존 tests/test_af_contract_dashboard.py, test_step23_2/3의 관례를 따라
dashboard.py UI 로직은 소스 검사 + 콜백 로직을 순수 함수로 재현해 검증한다.
실제 GPT/OpenAI 호출은 발생시키지 않는다.
"""
import inspect
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import modules.app_factory as af_mod

_DASHBOARD_SRC = (Path(__file__).resolve().parent.parent / "dashboard.py").read_text(encoding="utf-8")


# ── dashboard.py의 _af_suggest_fields_with_ai() 콜백 로직 재현 (UI 없이) ──────

def _apply_suggestion(spec: dict, prior_input: str = "", prior_output: str = "", prior_formula: str = "") -> dict:
    """dashboard.py의 콜백 본문(필드/필드/formula 반영 부분)을 순수 함수로 재현."""
    state = {
        "af_contract_input_fields": prior_input,
        "af_contract_output_fields": prior_output,
        "af_contract_formula": prior_formula,
    }
    in_keys = list((spec.get("input_schema") or {}).keys())
    out_keys = list((spec.get("output_schema") or {}).keys())
    if not in_keys and not out_keys:
        return state  # 실패 취급, 기존 값 보존
    if in_keys:
        state["af_contract_input_fields"] = ", ".join(in_keys)
    if out_keys:
        state["af_contract_output_fields"] = ", ".join(out_keys)
    formula = spec.get("formula")
    has_formula = formula not in (None, "", {})
    if has_formula:
        f_str = json.dumps(formula, ensure_ascii=False) if isinstance(formula, dict) else str(formula)
        state["af_contract_formula"] = f_str
    return state


def _bmi_spec():
    return {
        "calculator_type": "BMI 계산기",
        "input_schema": {"height_cm": "number", "weight_kg": "number"},
        "output_schema": {"bmi": "number"},
        "formula": "weight_kg / (height_cm/100) ** 2",
        "labels": {"height_cm": "키", "weight_kg": "몸무게", "bmi": "BMI"},
        "_formula_valid": True, "_formula_msg": "OK",
    }


# ── Test 1~3: 필드/라벨 추출 ──────────────────────────────────────────────

class TestFieldExtraction:
    def test_1_input_field_names_extracted(self):
        state = _apply_suggestion(_bmi_spec())
        assert state["af_contract_input_fields"] == "height_cm, weight_kg"

    def test_2_output_field_names_extracted(self):
        state = _apply_suggestion(_bmi_spec())
        assert state["af_contract_output_fields"] == "bmi"

    def test_3_labels_not_forced_into_contract_fields(self):
        """build_contract()에 label 파라미터가 없으므로(Contract는 필드명만 Lock),
        label은 입력란에 직접 채우지 않고 성공 메시지에만 참고용으로 표시되어야 한다."""
        sig = inspect.signature(af_mod.build_contract)
        assert "label" not in sig.parameters
        assert "labels" not in sig.parameters


# ── Test 4~5: formula 반영/보존 ────────────────────────────────────────────

class TestFormulaHandling:
    def test_4_valid_formula_applied(self):
        state = _apply_suggestion(_bmi_spec())
        assert state["af_contract_formula"] == "weight_kg / (height_cm/100) ** 2"

    def test_5_empty_formula_preserves_existing(self):
        spec = dict(_bmi_spec())
        spec["formula"] = ""
        state = _apply_suggestion(spec, prior_formula="years_of_service * 2")
        assert state["af_contract_formula"] == "years_of_service * 2"

    def test_5b_none_formula_preserves_existing(self):
        spec = dict(_bmi_spec())
        spec["formula"] = None
        state = _apply_suggestion(spec, prior_formula="existing_formula")
        assert state["af_contract_formula"] == "existing_formula"

    def test_5c_empty_dict_formula_preserves_existing(self):
        spec = dict(_bmi_spec())
        spec["formula"] = {}
        state = _apply_suggestion(spec, prior_formula="existing_formula")
        assert state["af_contract_formula"] == "existing_formula"

    def test_5d_dict_formula_serialized_as_json(self):
        spec = dict(_bmi_spec())
        spec["formula"] = {"a": "x + y", "b": "x - y"}
        state = _apply_suggestion(spec)
        assert json.loads(state["af_contract_formula"]) == {"a": "x + y", "b": "x - y"}


# ── Test 6: AI 실패 시 기존 값 보존 ────────────────────────────────────────

class TestFailureSafety:
    def test_6_no_fields_in_spec_preserves_existing(self):
        """input_schema/output_schema가 모두 비면(AI 실패/malformed 응답) 기존 값 보존."""
        empty_spec = {"input_schema": {}, "output_schema": {}, "formula": None}
        state = _apply_suggestion(
            empty_spec, prior_input="a, b", prior_output="c", prior_formula="a+b",
        )
        assert state["af_contract_input_fields"] == "a, b"
        assert state["af_contract_output_fields"] == "c"
        assert state["af_contract_formula"] == "a+b"

    def test_6b_exception_path_has_safe_fallback_message(self):
        """dashboard.py 콜백 소스에 예외 처리(try/except)와 안내 문구가 있는지."""
        cb_idx = _DASHBOARD_SRC.find("_af_suggest_fields_with_ai")
        cb_block = _DASHBOARD_SRC[cb_idx:cb_idx + 2500]
        assert "except Exception" in cb_block
        assert "기존 입력값은 유지됩니다" in cb_block


# ── Test 7: 버튼을 누르지 않은 rerun에서 AI 호출 없음 ─────────────────────

class TestNoAutoCallOnRerun:
    def test_7_suggest_spec_call_only_inside_callback(self):
        """AF._suggest_spec( 호출이 콜백 함수 정의 내부에만 있어야 한다
        (모듈 최상위/버튼 밖에서 무조건 실행되면 매 rerun마다 AI가 호출됨)."""
        cb_start = _DASHBOARD_SRC.find("def _af_suggest_fields_with_ai")
        cb_end = _DASHBOARD_SRC.find("\n        st.button(", cb_start)
        assert cb_start != -1 and cb_end != -1
        cb_body = _DASHBOARD_SRC[cb_start:cb_end]
        assert "AF._suggest_spec(" in cb_body
        # 콜백 밖(버튼 정의 이후 다음 버튼까지) 에는 호출이 없어야 함
        after_btn = _DASHBOARD_SRC[cb_end:cb_end + 400]
        assert "AF._suggest_spec(" not in after_btn

    def test_7b_button_uses_on_click_not_if_block(self):
        """on_click 콜백 패턴이어야 매 rerun마다 자동 실행되지 않는다
        (버튼 클릭 시에만 Streamlit이 콜백을 실행)."""
        btn_idx = _DASHBOARD_SRC.find('"💡 필드 자동 제안"')
        btn_block = _DASHBOARD_SRC[btn_idx:btn_idx + 300]
        assert "on_click=_af_suggest_fields_with_ai" in btn_block


# ── Test 8~10: 사용자 override 보존 ────────────────────────────────────────

class TestUserOverridePreserved:
    def test_8_input_fields_write_only_inside_callback(self):
        cb_start = _DASHBOARD_SRC.find("def _af_suggest_fields_with_ai")
        btn_start = _DASHBOARD_SRC.find('st.button(\n            "💡 필드 자동 제안"')
        write_idx = _DASHBOARD_SRC.find('st.session_state["af_contract_input_fields"] = ", ".join(_in_keys)')
        assert -1 not in (cb_start, btn_start, write_idx)
        assert cb_start < write_idx < btn_start

    def test_9_output_fields_write_only_inside_callback(self):
        cb_start = _DASHBOARD_SRC.find("def _af_suggest_fields_with_ai")
        btn_start = _DASHBOARD_SRC.find('st.button(\n            "💡 필드 자동 제안"')
        write_idx = _DASHBOARD_SRC.find('st.session_state["af_contract_output_fields"] = ", ".join(_out_keys)')
        assert -1 not in (cb_start, btn_start, write_idx)
        assert cb_start < write_idx < btn_start

    def test_10_formula_write_only_inside_callback(self):
        cb_start = _DASHBOARD_SRC.find("def _af_suggest_fields_with_ai")
        btn_start = _DASHBOARD_SRC.find('"💡 필드 자동 제안"')
        # 동일 문자열이 기존 _af_load_contract_instance 콜백(STEP24-2 이전 코드)에도
        # 존재하므로 반드시 cb_start 이후에서만 검색해야 한다.
        write_idx = _DASHBOARD_SRC.find('st.session_state["af_contract_formula"] = _f_str', cb_start)
        assert -1 not in (cb_start, btn_start, write_idx)
        assert cb_start < write_idx < btn_start
        # 입력 위젯(text_input/text_area) 자체에 value=가 강제되지 않아야 사용자가
        # 이후 직접 수정한 값이 override로 유지된다(STEP23-2/23-3과 동일 원칙).
        for key in ("af_contract_input_fields", "af_contract_output_fields", "af_contract_formula"):
            widget_idx = _DASHBOARD_SRC.find(f'key="{key}"')
            assert widget_idx != -1
            widget_block = _DASHBOARD_SRC[max(0, widget_idx - 300):widget_idx + 50]
            assert "value=" not in widget_block.split("st.text_")[-1]


# ── Test 11~13: Mode A / Contract 생성 / Tier2-B 무영향 ───────────────────

class TestModeAAndContractAndTier2BUnaffected:
    def test_11_mode_a_generate_app_call_unchanged(self):
        mode_a_idx = _DASHBOARD_SRC.find("# ── Mode A: 자동 생성")
        mode_b_idx = _DASHBOARD_SRC.find("# ── Mode B: Contract 기반 생성")
        mode_a_block = _DASHBOARD_SRC[mode_a_idx:mode_b_idx]
        assert "_af_suggest_fields_with_ai" not in mode_a_block
        assert "AF._suggest_spec" not in mode_a_block
        assert "generate_app(" in mode_a_block.replace(" ", "")

    def test_12_contract_gen_button_call_unchanged(self):
        """'📋 Contract 기반 생성' 버튼의 호출 흐름(build_contract → generate_app_with_contract)
        이 이번 STEP으로 변경되지 않았는지."""
        gen_idx = _DASHBOARD_SRC.find('st.button("📋 Contract 기반 생성"')
        next_top_level_idx = _DASHBOARD_SRC.find("\n    app = st.session_state.get(\"af_result\")", gen_idx)
        assert gen_idx != -1 and next_top_level_idx != -1
        gen_block = _DASHBOARD_SRC[gen_idx:next_top_level_idx]
        assert "AF.build_contract(" in gen_block
        assert "generate_app_with_contract(" in gen_block
        assert "_af_suggest_fields_with_ai" not in gen_block

    def test_13_tier2b_checkbox_wiring_unchanged(self):
        """STEP23-2의 Tier2-B 배선(af_tier2b_suggested/af_contract_is_tier2b)이
        이번 STEP으로 손상되지 않았는지 — 여전히 AI Tier 추천 버튼 핸들러 내부에만 존재."""
        tier_btn_idx = _DASHBOARD_SRC.find('st.button("💡 Tier AI 추천"')
        write_idx = _DASHBOARD_SRC.find('st.session_state["af_contract_is_tier2b"] =')
        checkbox_idx = _DASHBOARD_SRC.find('key="af_contract_is_tier2b"')
        assert -1 not in (tier_btn_idx, write_idx, checkbox_idx)
        assert tier_btn_idx < write_idx < checkbox_idx
        # 필드 제안 콜백이 이 배선을 건드리지 않는지
        cb_start = _DASHBOARD_SRC.find("def _af_suggest_fields_with_ai")
        cb_end = _DASHBOARD_SRC.find("\n        st.button(", cb_start)
        cb_body = _DASHBOARD_SRC[cb_start:cb_end]
        assert "af_contract_is_tier2b" not in cb_body
        assert "af_tier2b_suggested" not in cb_body


# ── Test 14~15: 무관 모듈/Registry/Contract schema/DB 무변경 ──────────────

class TestNoUnrelatedModuleChanges:
    def test_14_review_center_and_formula_engine_untouched(self):
        """이번 STEP은 dashboard.py + 신규 테스트 파일만 변경 대상이므로,
        review_center.py/formula_engine.py에 STEP24-2 관련 마커가 없어야 한다."""
        import modules.review_center as rc_mod
        import modules.formula_engine as fe_mod
        assert "STEP 24-2" not in inspect.getsource(rc_mod)
        assert "STEP 24-2" not in inspect.getsource(fe_mod)
        assert "_af_suggest_fields_with_ai" not in inspect.getsource(rc_mod)
        assert "_af_suggest_fields_with_ai" not in inspect.getsource(fe_mod)

    def test_15_suggest_spec_itself_unmodified_by_this_step(self):
        """_suggest_spec()은 STEP24-1에서 이미 검증된 함수 — 이번 STEP은
        이를 '재사용'만 해야 하므로 그 내부에 STEP24-2 마커가 있으면 안 된다."""
        src = inspect.getsource(af_mod._suggest_spec)
        assert "STEP 24-2" not in src
