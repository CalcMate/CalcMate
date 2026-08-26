# -*- coding: utf-8 -*-
"""tests/test_step24_1_suggest_spec_extraction.py — STEP 24-1 회귀 테스트

STEP 24-1 변경: modules/app_factory.py의 generate_app() 내부 스펙 설계 로직
(sys1/u1 GPT 호출 + formula 검증/재시도)을 _suggest_spec() 헬퍼로 순수 추출했다.
프롬프트/검증/재시도 로직은 한 글자도 바뀌지 않았으며, generate_app()은 이제
_suggest_spec()을 호출해 동일한 결과를 얻는다.

이번 STEP의 목표는 "필드 자동 제안 UI 구현"이 아니라 리팩터 자체의 무손상 검증이므로,
테스트도 (a) _suggest_spec()이 독립적으로 기대 스키마를 반환하는지,
(b) generate_app()이 이 헬퍼를 실제로 호출하는 구조인지,
(c) Mode A(_contract=None) 경로가 완전히 보존되는지에 집중한다.

실제 GPT/OpenAI 호출은 발생시키지 않는다 — modules.app_factory._chat을 mock한다.
"""
import inspect
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import modules.app_factory as af_mod


def _mock_chat_spec(calculator_type="BMI 계산기", input_schema=None, output_schema=None,
                     formula="weight_kg / (height_cm/100) ** 2", labels=None):
    """_chat()이 반환하는 (text, model, tokens) 튜플을 재현."""
    payload = {
        "calculator_type": calculator_type,
        "input_schema": input_schema or {"height_cm": "number", "weight_kg": "number"},
        "output_schema": output_schema or {"bmi": "number"},
        "formula": formula,
        "labels": labels or {"height_cm": "키", "weight_kg": "몸무게", "bmi": "BMI"},
    }
    return (json.dumps(payload, ensure_ascii=False), "gpt-4o", 123)


# ── 1. _suggest_spec()이 기대 schema를 반환하는지 ────────────────────────────

class TestSuggestSpecReturnsExpectedSchema:
    def test_1_returns_spec_and_steps_tuple(self):
        with patch("modules.app_factory._chat", return_value=_mock_chat_spec()):
            spec, steps = af_mod._suggest_spec(
                cfg={}, name="BMI 계산기", category="건강", desc="키/몸무게로 BMI 계산",
                tier=2, existing=[], _contract=None,
            )
        assert isinstance(spec, dict)
        assert isinstance(steps, list)

    def test_2_input_schema_preserved(self):
        with patch("modules.app_factory._chat", return_value=_mock_chat_spec()):
            spec, _ = af_mod._suggest_spec({}, "BMI 계산기", "", "", 2, [])
        assert spec["input_schema"] == {"height_cm": "number", "weight_kg": "number"}

    def test_3_output_schema_preserved(self):
        with patch("modules.app_factory._chat", return_value=_mock_chat_spec()):
            spec, _ = af_mod._suggest_spec({}, "BMI 계산기", "", "", 2, [])
        assert spec["output_schema"] == {"bmi": "number"}

    def test_4_labels_preserved(self):
        with patch("modules.app_factory._chat", return_value=_mock_chat_spec()):
            spec, _ = af_mod._suggest_spec({}, "BMI 계산기", "", "", 2, [])
        assert spec["labels"] == {"height_cm": "키", "weight_kg": "몸무게", "bmi": "BMI"}

    def test_5_formula_preserved(self):
        with patch("modules.app_factory._chat", return_value=_mock_chat_spec()):
            spec, _ = af_mod._suggest_spec({}, "BMI 계산기", "", "", 2, [])
        assert spec["formula"] == "weight_kg / (height_cm/100) ** 2"

    def test_5b_formula_validation_flags_set(self):
        """기존 [2] 검증 로직이 헬퍼 안에서 여전히 _formula_valid/_formula_msg를 채우는지."""
        with patch("modules.app_factory._chat", return_value=_mock_chat_spec()):
            spec, _ = af_mod._suggest_spec({}, "BMI 계산기", "", "", 2, [])
        assert "_formula_valid" in spec
        assert "_formula_msg" in spec
        assert spec["_formula_valid"] is True

    def test_6_steps_contains_spec_stage(self):
        with patch("modules.app_factory._chat", return_value=_mock_chat_spec()):
            _, steps = af_mod._suggest_spec({}, "BMI 계산기", "", "", 2, [])
        assert steps[0][0] == "총괄(스펙)"


# ── 2. generate_app()이 헬퍼를 호출하는 구조인지 (소스 검사) ─────────────────

class TestGenerateAppUsesHelper:
    def test_7_generate_app_calls_suggest_spec(self):
        src = inspect.getsource(af_mod.generate_app)
        assert "_suggest_spec(" in src, "generate_app()이 _suggest_spec()을 호출하지 않음"
        # sys1 프롬프트 원문이 generate_app() 안에 더 이상 직접 존재하면 안 됨(중복 방지 확인)
        assert "너는 웹 계산기 기획자다" not in src, (
            "sys1 프롬프트가 generate_app()에 남아있음 — 순수 추출이 아니라 복사됨"
        )

    def test_8_suggest_spec_prompt_unchanged(self):
        """sys1 프롬프트 원문이 헬퍼 안에 정확히 보존되어 있는지(문구 변경 여부 확인)."""
        src = inspect.getsource(af_mod._suggest_spec)
        assert "너는 웹 계산기 기획자다" in src
        assert "허용 함수: min, max, round, abs, int, float 만 사용 가능" in src
        assert '{"calculator_type":"","input_schema":{},"output_schema":{},"formula":"또는{}","labels":{}}' in src

    def test_9_retry_logic_preserved_in_helper(self):
        src = inspect.getsource(af_mod._suggest_spec)
        assert "[재설계]" in src
        assert "총괄(재시도)" in src


# ── 3. Mode A(_contract=None) 경로 및 시그니처 보존 ──────────────────────────

class TestModeAPreserved:
    def test_10_generate_app_signature_unchanged(self):
        sig = str(inspect.signature(af_mod.generate_app))
        assert sig == "(cfg: dict, name: str, category: str = '', desc: str = '', tier: int = 2, _contract: dict = None) -> dict"

    def test_11_mode_a_full_pipeline_uses_helper_result(self):
        """generate_app() 전체 파이프라인을 mock으로 실행해 Mode A(_contract=None)
        결과가 _suggest_spec()의 spec을 그대로 반영하는지 확인."""
        existing_calc_repo_patch = patch(
            "modules.app_factory.CalculatorRepository",
        )
        with existing_calc_repo_patch as MockRepo:
            MockRepo.return_value.get_all.return_value = []
            with patch("modules.app_factory._chat") as mock_chat:
                # 1) 스펙 설계, 2) HTML, 3) SEO/FAQ, 4) 이미지프롬프트 순서로 호출된다고 가정
                mock_chat.side_effect = [
                    _mock_chat_spec(),
                    ("<html></html>", "claude", 10),
                    (json.dumps({"seo_title": "t", "seo_desc": "d", "faq": [], "blog_draft": ""},
                                ensure_ascii=False), "gpt-4o", 10),
                    (json.dumps({"image_prompt_thumbnail": "", "image_prompt_body": ""},
                                ensure_ascii=False), "gpt-4o", 10),
                ]
                app = af_mod.generate_app(
                    cfg={}, name="BMI 계산기", category="건강",
                    desc="키/몸무게로 BMI 계산", tier=2, _contract=None,
                )
        assert app["input_schema"] == {"height_cm": "number", "weight_kg": "number"}
        assert app["output_schema"] == {"bmi": "number"}
        assert app.get("_contract") is None or "_contract" not in app or app.get("_contract") in (None,)

    def test_12_existing_list_passed_through_to_helper(self):
        """[0] 기존 계산기 로드 결과(existing)가 헬퍼에 그대로 전달되는지(중복회피 컨텍스트 보존)."""
        src = inspect.getsource(af_mod.generate_app)
        idx_load = src.find("CalculatorRepository")
        idx_call = src.find("= _suggest_spec(")  # 실제 호출부(주석의 "_suggest_spec()" 언급과 구분)
        assert idx_load != -1 and idx_call != -1
        assert idx_load < idx_call, "existing 로드가 _suggest_spec 호출보다 먼저 있어야 함"
        assert "existing" in src[idx_call:idx_call + 60]
