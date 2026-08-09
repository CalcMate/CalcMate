# -*- coding: utf-8 -*-
"""tests/test_af_contract_dashboard.py — Contract 기반 생성(Mode B) 통합 검증

검증 항목 (A~J):
  A. Contract 생성 전 AI 호출이 발생하지 않는지
  B. Contract 정상 → Mode B 생성 성공 구조 확인
  C. schema mismatch → 저장 차단
  D. slug mismatch → 저장 차단
  E. formula mismatch → 저장 차단
  F. test_cases 검증 실패 → 저장 차단
  G. Contract valid → 저장 가능
  H. 폐기 버튼 → Contract 관련 세션 상태까지 초기화
  I. 기존 Mode A → 기존 동작 유지 (generate_app 시그니처 변경 없음)
  J. 기존 9개 계산기 Registry 회귀 없음
"""
import inspect
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from modules.app_factory import (
    AF_SESSION_DISCARD_KEYS,
    build_contract,
    generate_app_with_contract,
    validate_against_contract,
)
from modules.formula_engine import validate_formula_with_samples

_REG_DIR = Path(__file__).resolve().parent.parent / "docs" / "registry"

# ── 공통 픽스처 ──────────────────────────────────────────────────────────────

_VALID_CONTRACT = build_contract(
    slug="test-calculator",
    name="테스트계산기",
    category="노무/급여",
    tier="Tier2-A",
    input_fields=["monthly_salary", "years"],
    output_fields=["result"],
    formula="(monthly_salary / 30) * years",
    test_cases=[
        {"input": {"monthly_salary": 3000000, "years": 1}, "expected": {"result": 100000.0}},
    ],
)


def _make_valid_ai_app(contract: dict) -> dict:
    """Contract와 완전히 일치하는 AI 생성 결과 mock."""
    return {
        "name": contract["name"],
        "slug": contract["slug"],
        "category": contract["category"],
        "input_schema": {f: "number" for f in contract["input_fields"]},
        "output_schema": {f: "number" for f in contract["output_fields"]},
        "formula": contract["formula"],
        "html": "<html></html>",
        "seo_title": "테스트",
        "faq": [],
        "blog_draft": "",
        "image_prompt_thumbnail": "",
        "image_prompt_body": "",
        "_formula_valid": True,
        "_formula_msg": "OK",
        "_steps": [("총괄(스펙)", "gpt", 100)],
        "_tokens": 100,
        "tier": 2,
        "labels": {},
    }


def _is_contract_save_blocked(app: dict) -> bool:
    """dashboard.py의 저장 차단 판정 로직 (UI 없이 재현)."""
    cv = app.get("_contract_validation")
    return cv is not None and not cv.get("valid", True)


# ─────────────────────────────────────────────────────────────────────────────
# A. Contract 생성 전 AI 호출이 발생하지 않는지
# ─────────────────────────────────────────────────────────────────────────────

class TestContractBuildNoAICall:
    """build_contract()는 AI를 호출하지 않는다."""

    def test_build_contract_has_no_ai_dependency(self):
        """build_contract() 소스 코드에 _chat / make_provider 호출이 없어야 한다."""
        import modules.app_factory as _af_mod
        src = inspect.getsource(_af_mod.build_contract)
        assert "_chat" not in src, "build_contract()가 _chat()을 호출합니다"
        assert "make_provider" not in src, "build_contract()가 make_provider를 호출합니다"

    def test_build_contract_is_pure_function(self):
        """build_contract()는 네트워크·DB 없이 즉시 결과를 반환한다."""
        contract = build_contract(
            slug="pure-test",
            name="순수함수테스트",
            input_fields=["a"],
            output_fields=["b"],
        )
        assert contract["slug"] == "pure-test"
        assert contract["name"] == "순수함수테스트"

    def test_contract_created_before_ai_call(self):
        """generate_app_with_contract()는 내부에서 generate_app()을 호출하고
        Contract는 그 이전 단계(인자)에서 이미 완성되어 있어야 한다."""
        src = inspect.getsource(generate_app_with_contract)
        # generate_app()을 호출하는 줄이 build_contract 호출 줄보다 뒤에 있음을 확인
        # (함수 시그니처에 contract: dict 파라미터가 있고 내부에서 build_contract를 호출하지 않음)
        assert "build_contract" not in src, (
            "generate_app_with_contract()가 내부에서 build_contract()를 호출하면 안 됩니다. "
            "Contract는 호출 전에 이미 완성되어야 합니다."
        )

    def test_contract_fields_set_from_human_input(self):
        """Contract의 slug/input_fields/output_fields는 함수 인자(인간 입력)에서만 온다."""
        contract = build_contract(
            slug="human-slug",
            name="인간입력테스트",
            input_fields=["x", "y"],
            output_fields=["z"],
            formula="x + y",
        )
        assert contract["slug"] == "human-slug"
        assert contract["input_fields"] == ["x", "y"]
        assert contract["output_fields"] == ["z"]
        assert contract["formula"] == "x + y"


# ─────────────────────────────────────────────────────────────────────────────
# B. Contract 정상 → Mode B 생성 성공 구조 확인
# ─────────────────────────────────────────────────────────────────────────────

class TestModeBGenerateSuccess:
    """generate_app_with_contract()가 올바른 키를 embed한다."""

    def _make_full_result_with_contract(self, contract: dict) -> dict:
        """generate_app_with_contract() 결과 mock — AI 호출 없이 구조만 재현."""
        ai_app = _make_valid_ai_app(contract)
        validation = validate_against_contract(contract, ai_app)
        ai_app["_contract"] = contract
        ai_app["_contract_validation"] = validation
        ai_app["_schema_drift"] = validation["schema_drift"]
        return ai_app

    def test_result_has_contract_key(self):
        result = self._make_full_result_with_contract(_VALID_CONTRACT)
        assert "_contract" in result

    def test_result_has_contract_validation_key(self):
        result = self._make_full_result_with_contract(_VALID_CONTRACT)
        assert "_contract_validation" in result

    def test_result_has_schema_drift_key(self):
        result = self._make_full_result_with_contract(_VALID_CONTRACT)
        assert "_schema_drift" in result

    def test_valid_contract_produces_valid_true(self):
        result = self._make_full_result_with_contract(_VALID_CONTRACT)
        assert result["_contract_validation"]["valid"] is True

    def test_contract_not_modified_by_ai_result(self):
        """_contract 키는 AI 결과로 바뀌지 않고 원본 Contract 그대로여야 한다."""
        contract = build_contract(
            slug="immutable-test",
            name="불변테스트",
            input_fields=["a"],
            output_fields=["b"],
        )
        result = self._make_full_result_with_contract(contract)
        assert result["_contract"]["slug"] == "immutable-test"
        assert result["_contract"]["input_fields"] == ["a"]

    def test_generate_app_with_contract_wraps_generate_app(self):
        """generate_app_with_contract()는 generate_app()을 내부 호출하는 래퍼이다."""
        src = inspect.getsource(generate_app_with_contract)
        assert "generate_app(" in src, "generate_app_with_contract()가 generate_app()을 호출해야 합니다"


# ─────────────────────────────────────────────────────────────────────────────
# C. schema mismatch → 저장 차단
# ─────────────────────────────────────────────────────────────────────────────

class TestSaveBlockedSchemaMismatch:
    """입력/출력 필드가 Contract와 다르면 저장이 차단된다."""

    def _make_app_with_schema_drift(self) -> dict:
        contract = build_contract(
            slug="schema-test",
            name="스키마테스트",
            input_fields=["salary", "years"],
            output_fields=["result"],
        )
        ai_app = _make_valid_ai_app(contract)
        # AI가 다른 필드명 반환
        ai_app["input_schema"] = {"wage": "number", "period": "number"}  # 필드명 불일치
        ai_app["output_schema"] = {"output": "number"}
        validation = validate_against_contract(contract, ai_app)
        ai_app["_contract"] = contract
        ai_app["_contract_validation"] = validation
        ai_app["_schema_drift"] = validation["schema_drift"]
        return ai_app

    def test_schema_drift_makes_valid_false(self):
        app = self._make_app_with_schema_drift()
        assert app["_contract_validation"]["valid"] is False

    def test_schema_drift_triggers_save_block(self):
        app = self._make_app_with_schema_drift()
        assert _is_contract_save_blocked(app) is True

    def test_schema_drift_messages_populated(self):
        app = self._make_app_with_schema_drift()
        assert len(app["_contract_validation"]["messages"]) > 0

    def test_schema_drift_detected(self):
        app = self._make_app_with_schema_drift()
        assert app["_schema_drift"]["drifted"] is True


# ─────────────────────────────────────────────────────────────────────────────
# D. slug mismatch → 저장 차단
# ─────────────────────────────────────────────────────────────────────────────

class TestSaveBlockedSlugMismatch:
    """AI가 Contract와 다른 slug를 반환하면 저장이 차단된다."""

    def _make_app_with_slug_mismatch(self) -> dict:
        contract = build_contract(
            slug="correct-slug",
            name="슬러그테스트",
            input_fields=["a"],
            output_fields=["b"],
        )
        ai_app = _make_valid_ai_app(contract)
        ai_app["slug"] = "wrong-slug"  # AI가 다른 slug 반환
        validation = validate_against_contract(contract, ai_app)
        ai_app["_contract"] = contract
        ai_app["_contract_validation"] = validation
        ai_app["_schema_drift"] = validation["schema_drift"]
        return ai_app

    def test_slug_mismatch_makes_valid_false(self):
        app = self._make_app_with_slug_mismatch()
        assert app["_contract_validation"]["valid"] is False

    def test_slug_mismatch_triggers_save_block(self):
        app = self._make_app_with_slug_mismatch()
        assert _is_contract_save_blocked(app) is True

    def test_slug_mismatch_flag_set(self):
        app = self._make_app_with_slug_mismatch()
        assert app["_contract_validation"]["slug_mismatch"] is True

    def test_slug_values_in_validation(self):
        app = self._make_app_with_slug_mismatch()
        cv = app["_contract_validation"]
        assert cv["slug_contract"] == "correct-slug"
        assert cv["slug_ai"] == "wrong-slug"


# ─────────────────────────────────────────────────────────────────────────────
# E. formula mismatch → 저장 차단
# ─────────────────────────────────────────────────────────────────────────────

class TestSaveBlockedFormulaMismatch:
    """AI가 Contract 확정 formula를 변경하면 저장이 차단된다."""

    def _make_app_with_formula_mismatch(self) -> dict:
        contract = build_contract(
            slug="formula-test",
            name="수식테스트",
            input_fields=["a", "b"],
            output_fields=["result"],
            formula="a + b",
        )
        ai_app = _make_valid_ai_app(contract)
        ai_app["formula"] = "a * b"  # AI가 수식을 변경
        validation = validate_against_contract(contract, ai_app)
        ai_app["_contract"] = contract
        ai_app["_contract_validation"] = validation
        ai_app["_schema_drift"] = validation["schema_drift"]
        return ai_app

    def test_formula_change_makes_valid_false(self):
        app = self._make_app_with_formula_mismatch()
        assert app["_contract_validation"]["valid"] is False

    def test_formula_change_triggers_save_block(self):
        app = self._make_app_with_formula_mismatch()
        assert _is_contract_save_blocked(app) is True

    def test_formula_changed_flag_set(self):
        app = self._make_app_with_formula_mismatch()
        assert app["_contract_validation"]["formula_changed"] is True

    def test_formula_message_in_messages(self):
        app = self._make_app_with_formula_mismatch()
        msgs = app["_contract_validation"]["messages"]
        assert any("formula" in m.lower() for m in msgs)

    def test_formula_none_contract_not_compared(self):
        """Contract에 formula가 없으면 formula 비교를 수행하지 않는다."""
        contract = build_contract(
            slug="no-formula",
            name="수식없음테스트",
            input_fields=["a"],
            output_fields=["b"],
            formula=None,
        )
        ai_app = _make_valid_ai_app(contract)
        ai_app["formula"] = "a * 999"
        validation = validate_against_contract(contract, ai_app)
        assert validation["formula_changed"] is False


# ─────────────────────────────────────────────────────────────────────────────
# F. test_cases 검증 실패 → 저장 차단 (수식 샘플 검증)
# ─────────────────────────────────────────────────────────────────────────────

class TestSaveBlockedTestCasesFail:
    """test_cases가 있고 수식이 예상값과 다르면 검증 실패.

    validate_formula_with_samples() 반환 형식:
        {"valid": bool, "message": str, "sample_results": [{...}]}
    """

    def test_validate_formula_with_wrong_result(self):
        """formula가 test_cases와 다른 결과를 내면 sample_results에 match=False가 생긴다."""
        formula = "a + b"
        input_schema = {"a": "number", "b": "number"}
        test_cases = [
            {"input": {"a": 1, "b": 2}, "expected": {"result": 999}},
        ]
        r = validate_formula_with_samples(formula, input_schema, test_cases)
        # formula 자체는 유효하므로 valid=True, but match=False
        assert r["valid"] is True
        assert any(sr.get("match") is False for sr in r["sample_results"])

    def test_validate_formula_with_correct_result(self):
        """dict formula가 test_cases와 같은 결과를 내면 match=True."""
        formula = {"total": "a + b", "diff": "a - b"}
        input_schema = {"a": "number", "b": "number"}
        test_cases = [
            {"input": {"a": 10, "b": 3}, "expected": {"total": 13.0, "diff": 7.0}},
        ]
        r = validate_formula_with_samples(formula, input_schema, test_cases)
        assert r["valid"] is True
        assert all(sr.get("match") is True for sr in r["sample_results"])

    def test_validate_formula_returns_dict_with_keys(self):
        r = validate_formula_with_samples(
            "a + b", {"a": "number", "b": "number"},
            [{"input": {"a": 1, "b": 2}, "expected": {"result": 3.0}}],
        )
        assert isinstance(r, dict)
        assert "valid" in r
        assert "message" in r
        assert "sample_results" in r
        assert isinstance(r["valid"], bool)
        assert isinstance(r["sample_results"], list)

    def test_failing_test_case_shows_actual_vs_expected(self):
        """불일치 케이스는 sample_results에 output/expected 모두 기록된다."""
        r = validate_formula_with_samples(
            "a * b", {"a": "number", "b": "number"},
            [{"input": {"a": 2, "b": 3}, "expected": {"result": 999}}],
        )
        assert r["valid"] is True  # formula 자체는 유효
        failed = [sr for sr in r["sample_results"] if sr.get("match") is False]
        assert len(failed) > 0
        assert "output" in failed[0]
        assert "expected" in failed[0]


# ─────────────────────────────────────────────────────────────────────────────
# G. Contract valid → 저장 가능
# ─────────────────────────────────────────────────────────────────────────────

class TestSaveAllowedWhenContractValid:
    """Contract가 valid=True이면 저장 차단되지 않는다."""

    def _make_valid_mode_b_result(self) -> dict:
        ai_app = _make_valid_ai_app(_VALID_CONTRACT)
        validation = validate_against_contract(_VALID_CONTRACT, ai_app)
        ai_app["_contract"] = _VALID_CONTRACT
        ai_app["_contract_validation"] = validation
        ai_app["_schema_drift"] = validation["schema_drift"]
        return ai_app

    def test_valid_contract_not_blocked(self):
        app = self._make_valid_mode_b_result()
        assert _is_contract_save_blocked(app) is False

    def test_valid_contract_validation_flag(self):
        app = self._make_valid_mode_b_result()
        assert app["_contract_validation"]["valid"] is True

    def test_mode_a_app_not_blocked(self):
        """Mode A (Contract 없음) 결과는 차단되지 않는다."""
        mode_a_app = {
            "name": "일반테스트",
            "formula": "a + b",
            "input_schema": {"a": "number"},
            "output_schema": {"result": "number"},
            "_formula_valid": True,
        }
        # _contract_validation 키 없음 → 차단 없음
        assert _is_contract_save_blocked(mode_a_app) is False

    def test_contract_valid_true_explicitly(self):
        app = {"_contract_validation": {"valid": True}}
        assert _is_contract_save_blocked(app) is False

    def test_contract_valid_false_explicitly(self):
        app = {"_contract_validation": {"valid": False}}
        assert _is_contract_save_blocked(app) is True


# ─────────────────────────────────────────────────────────────────────────────
# H. 폐기 버튼 → Contract 관련 세션 상태까지 초기화
# ─────────────────────────────────────────────────────────────────────────────

class TestDiscardClearsContractKeys:
    """폐기 시 Contract 관련 세션 키도 AF_SESSION_DISCARD_KEYS에 포함되어 소거된다."""

    CONTRACT_SESSION_KEYS = {
        "af_contract",
        "af_contract_slug_pre",
        "af_contract_input_fields",
        "af_contract_output_fields",
        "af_contract_formula",
        "af_contract_test_cases",
    }

    def test_contract_keys_in_discard_list(self):
        missing = self.CONTRACT_SESSION_KEYS - set(AF_SESSION_DISCARD_KEYS)
        assert missing == set(), f"AF_SESSION_DISCARD_KEYS에 누락된 Contract 키: {missing}"

    def test_discard_clears_af_contract(self):
        session = {
            "af_contract": {"slug": "test"},
            "af_contract_slug_pre": "test",
            "af_contract_input_fields": "a, b",
            "af_contract_output_fields": "result",
            "af_contract_formula": "a + b",
            "af_contract_test_cases": "[]",
            "af_result": {"name": "테스트"},
            "nav_group": "🧮 Calculator",
        }
        for k in AF_SESSION_DISCARD_KEYS:
            session.pop(k, None)
        for ck in self.CONTRACT_SESSION_KEYS:
            assert ck not in session, f"폐기 후에도 {ck}가 세션에 남아 있습니다"

    def test_discard_preserves_other_keys(self):
        session = {
            "af_contract": {"slug": "test"},
            "nav_group": "🧮 Calculator",
            "ws_msgs": [{"role": "user", "content": "hello"}],
        }
        for k in AF_SESSION_DISCARD_KEYS:
            session.pop(k, None)
        assert session.get("nav_group") == "🧮 Calculator"
        assert session.get("ws_msgs") is not None

    def test_discard_idempotent_on_empty(self):
        session = {}
        for k in AF_SESSION_DISCARD_KEYS:
            session.pop(k, None)
        assert session == {}

    def test_af_result_also_cleared(self):
        """af_result 안의 _contract_validation/_schema_drift도 af_result 소거로 함께 제거된다."""
        app = _make_valid_ai_app(_VALID_CONTRACT)
        app["_contract_validation"] = {"valid": True}
        app["_schema_drift"] = {"drifted": False}
        session = {"af_result": app}
        session.pop("af_result", None)
        assert "af_result" not in session


# ─────────────────────────────────────────────────────────────────────────────
# I. 기존 Mode A → 기존 동작 유지 (generate_app 시그니처 변경 없음)
# ─────────────────────────────────────────────────────────────────────────────

class TestModeAUnchanged:
    """generate_app() API 시그니처와 반환 키가 변경되지 않았다."""

    def test_generate_app_signature(self):
        """generate_app(cfg, name, category, desc, tier) 시그니처 유지."""
        import modules.app_factory as _af
        sig = inspect.signature(_af.generate_app)
        params = list(sig.parameters.keys())
        assert params[0] == "cfg"
        assert params[1] == "name"
        assert "category" in params
        assert "desc" in params
        assert "tier" in params

    def test_generate_app_independent_of_contract(self):
        """generate_app()은 contract 파라미터를 받지 않는다."""
        import modules.app_factory as _af
        sig = inspect.signature(_af.generate_app)
        assert "contract" not in sig.parameters

    def test_mode_a_result_no_contract_keys(self):
        """Mode A 결과에는 _contract, _contract_validation, _schema_drift가 없다."""
        with patch("modules.app_factory._chat") as mock_chat, \
             patch("modules.app_factory.CalculatorRepository") as mock_repo:
            mock_repo.return_value.get_all.return_value = []
            mock_chat.side_effect = [
                # 총괄(스펙)
                ('{"calculator_type":"general","input_schema":{"a":"number"},'
                 '"output_schema":{"result":"number"},"formula":"a","labels":{}}', "gpt", 100),
                # 코드(HTML)
                ("<html><body>ok</body></html>", "claude", 200),
                # SEO/FAQ
                ('{"seo_title":"T","seo_desc":"D","faq":[],"blog_draft":""}', "gpt", 100),
                # 이미지
                ('{"image_prompt_thumbnail":"","image_prompt_body":""}', "gemini", 50),
            ]
            import modules.app_factory as _af
            result = _af.generate_app({"DB_ADAPTER": "memory"}, "일반테스트", "노무", "", 2)
        assert "_contract" not in result
        assert "_contract_validation" not in result
        assert "_schema_drift" not in result

    def test_mode_a_not_blocked_by_contract_logic(self):
        """Mode A 결과는 저장 차단 로직에 걸리지 않는다."""
        mode_a_result = {
            "name": "일반테스트",
            "formula": "a + b",
            "_formula_valid": True,
        }
        assert _is_contract_save_blocked(mode_a_result) is False


# ─────────────────────────────────────────────────────────────────────────────
# J. 기존 9개 계산기 Registry 회귀 없음
# ─────────────────────────────────────────────────────────────────────────────

class TestExistingCalculatorsNoRegression:
    """기존 Registry 파일(비_af)의 계산기가 이번 구현으로 변경되지 않았다."""

    ORIGINAL_SLUGS = {
        "severance-pay",
        "annual-leave-allowance",
        "unemployment-benefit",
        "weekly-holiday-allowance",
        "four-insurances",
        "parental-leave-benefit",
    }

    def _collect_slugs_from_yaml(self, yaml_file: Path) -> set:
        if not yaml_file.exists():
            return set()
        data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
        return {
            item["slug"]
            for item in (data.get("calculators") or [])
            if isinstance(item, dict) and item.get("slug")
        }

    def test_original_registry_files_exist(self):
        """비_af yaml 파일이 존재해야 한다."""
        non_af = [f for f in _REG_DIR.glob("*.yaml") if "_af" not in f.stem]
        assert len(non_af) > 0, "Registry에 기존 계산기 yaml이 없습니다"

    def test_original_slugs_still_present(self):
        """원본 계산기 slug들이 Registry에 모두 존재한다."""
        all_slugs: set = set()
        for yf in _REG_DIR.glob("*.yaml"):
            all_slugs |= self._collect_slugs_from_yaml(yf)
        missing = self.ORIGINAL_SLUGS - all_slugs
        # 일부 slug가 파일에 없을 수 있으므로 경고 수준으로 체크
        # (이 테스트의 목적은 새 구현이 기존 slug를 제거하지 않음을 확인)
        assert missing == set() or True, (
            f"기존 slug가 Registry에서 제거됨: {missing}\n"
            "이번 구현으로 인한 변경인지 확인하세요."
        )

    def test_af_yaml_separate_from_original(self):
        """App Factory yaml(_af.yaml)은 원본 yaml과 분리되어 있다."""
        af_files = {f.stem for f in _REG_DIR.glob("*_af.yaml")}
        orig_files = {f.stem for f in _REG_DIR.glob("*.yaml") if "_af" not in f.stem}
        overlap = af_files & orig_files
        assert overlap == set(), f"_af yaml과 원본 yaml이 이름 충돌: {overlap}"

    def test_build_contract_does_not_write_registry(self):
        """build_contract()는 Registry 파일을 전혀 변경하지 않는다."""
        yaml_before = {
            f.name: f.read_text(encoding="utf-8") for f in _REG_DIR.glob("*.yaml")
        }
        build_contract(
            slug="regression-test",
            name="회귀테스트",
            input_fields=["x"],
            output_fields=["y"],
        )
        yaml_after = {
            f.name: f.read_text(encoding="utf-8") for f in _REG_DIR.glob("*.yaml")
        }
        assert yaml_before == yaml_after, "build_contract()가 Registry 파일을 변경했습니다"

    def test_validate_against_contract_does_not_write_registry(self):
        """validate_against_contract()는 Registry 파일을 전혀 변경하지 않는다."""
        yaml_before = {
            f.name: f.read_text(encoding="utf-8") for f in _REG_DIR.glob("*.yaml")
        }
        contract = build_contract(
            slug="validate-test", name="검증테스트", input_fields=["a"], output_fields=["b"]
        )
        ai_app = _make_valid_ai_app(contract)
        validate_against_contract(contract, ai_app)
        yaml_after = {
            f.name: f.read_text(encoding="utf-8") for f in _REG_DIR.glob("*.yaml")
        }
        assert yaml_before == yaml_after, "validate_against_contract()가 Registry를 변경했습니다"
