# -*- coding: utf-8 -*-
"""tests/test_step26_1_contract_slug_suggestion.py — STEP 26-1 회귀 테스트

STEP 26-1 변경: dashboard.py의 App Factory > Mode B(Contract 확정 스펙 입력)에서
계산기명(af_name) 입력 시 확정 slug(af_contract_slug_pre)를 기존 generate_slug()로
자동 제안한다. Mode A의 af_slug 자동 프리필과 동일한 함수를 재사용하며, 신규 slug
생성 규칙은 추가하지 않는다. 중복 확인도 기존 check_slug_conflict()를 그대로
재사용한다(dashboard.py는 st.session_state 기반 UI 스크립트라 실제 렌더링 없이는
단위 테스트가 어려우므로, 이 STEP의 정확한 로직을 순수 함수로 복제해 검증하고
dashboard.py 소스에 대해서는 구조/금지사항 검사를 수행한다 — STEP23~25 테스트와
동일한 패턴).

핵심 안전 원칙:
  slug 자동 제안 ≠ Contract 자동 확정 ≠ Contract 기반 생성 ≠ 저장 자동 실행.
  사용자가 한 번이라도 슬러그를 입력하면(자동 제안이든 직접 입력이든) 이후
  rerun에서 다시 덮어쓰지 않는다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from modules.slug_generator import generate_slug

_DASHBOARD_SRC = Path(__file__).resolve().parent.parent.joinpath("dashboard.py").read_text(encoding="utf-8")


def _contract_slug_block() -> str:
    """dashboard.py에서 STEP 26-1 Contract slug 자동 제안/중복확인 블록만 잘라낸다."""
    start = _DASHBOARD_SRC.find("# ── STEP 26-1: 확정 slug 자동 제안")
    end = _DASHBOARD_SRC.find("_af_input_fields = _bc2.text_input(", start)
    assert start != -1 and end != -1 and start < end, "STEP 26-1 Contract slug 블록을 찾지 못함"
    return _DASHBOARD_SRC[start:end]


def _prefill_contract_slug(af_name: str, current_slug: str) -> str:
    """dashboard.py의 STEP 26-1 프리필 로직을 그대로 복제한 순수 함수.

    실제 코드(dashboard.py):
        if af_name.strip() and not (st.session_state.get("af_contract_slug_pre") or "").strip():
            _cs_auto = generate_slug(af_name.strip())
            if _cs_auto:
                st.session_state["af_contract_slug_pre"] = _cs_auto
    """
    if (af_name or "").strip() and not (current_slug or "").strip():
        auto = generate_slug((af_name or "").strip())
        if auto:
            return auto
    return current_slug


# ── 1. 정상 slug 생성 ────────────────────────────────────────────────────────

class TestNormalSlugGeneration:
    def test_1_name_present_generates_slug(self):
        result = _prefill_contract_slug("퇴직금 계산기", "")
        assert result == "severance-pay"
        assert result != ""


# ── 2. 기존 generate_slug()와 동일한 결과 ────────────────────────────────────

class TestSameAsExistingGenerateSlug:
    def test_2_matches_generate_slug_directly(self):
        for name in ["퇴직금 계산기", "주휴수당 계산기", "4대보험 계산기", "BMI 계산기"]:
            assert _prefill_contract_slug(name, "") == generate_slug(name)


# ── 3. 빈 계산기명 처리 ──────────────────────────────────────────────────────

class TestEmptyNameSafe:
    def test_3_empty_name_no_exception_no_change(self):
        result = _prefill_contract_slug("", "")
        assert result == ""

    def test_3b_whitespace_only_name_no_change(self):
        result = _prefill_contract_slug("   ", "existing-slug")
        assert result == "existing-slug"


# ── 4. 사용자 입력값 보호 ────────────────────────────────────────────────────

class TestUserInputNotOverwritten:
    def test_4_existing_slug_not_overwritten(self):
        result = _prefill_contract_slug("퇴직금 계산기", "my-custom-slug")
        assert result == "my-custom-slug"


# ── 5. rerun 이후에도 override 유지 ──────────────────────────────────────────

class TestOverrideSurvivesRerun:
    def test_5_override_persists_across_simulated_reruns(self):
        # 1차 rerun: 이름만 있고 slug 비어있음 → 자동 제안
        slug_after_run1 = _prefill_contract_slug("퇴직금 계산기", "")
        assert slug_after_run1 == "severance-pay"

        # 사용자가 직접 수정(세션에 저장됐다고 가정)
        user_edited = "my-custom-slug"

        # 2차 rerun: 같은 이름, 사용자가 수정한 값이 session_state에 있음 → 유지
        slug_after_run2 = _prefill_contract_slug("퇴직금 계산기", user_edited)
        assert slug_after_run2 == user_edited

        # 3차 rerun: 이름이 바뀌어도 이미 채워진 슬러그는 여전히 보호됨
        slug_after_run3 = _prefill_contract_slug("주휴수당 계산기", slug_after_run2)
        assert slug_after_run3 == user_edited


# ── 6. 중복 slug 감지(기존 check_slug_conflict 재사용) ───────────────────────

class TestDuplicateDetectionReusesExisting:
    def test_6_block_calls_existing_check_slug_conflict(self):
        block = _contract_slug_block()
        assert "RC.check_slug_conflict(" in block


# ── 7. 중복 시 임의 변경 금지 ────────────────────────────────────────────────

class TestNoAutoRenameOnConflict:
    def test_7_no_random_or_numbered_slug_mutation(self):
        block = _contract_slug_block()
        for forbidden in ("uuid", "random", "secrets.", "-2\"", "+ '-'", "itertools"):
            assert forbidden not in block


# ── 8/9. 자동 생성·저장 직접 호출 금지 ───────────────────────────────────────

class TestNoAutoGenerationOrSave:
    def test_8_block_never_calls_generate_app(self):
        block = _contract_slug_block()
        assert "AF.generate_app(" not in block
        assert "AF.generate_app_with_contract(" not in block

    def test_9_block_never_calls_save_app(self):
        block = _contract_slug_block()
        assert "AF.save_app(" not in block


# ── 10. Mode A 기존 slug 흐름 무변경 ─────────────────────────────────────────

class TestModeAUnaffected:
    def test_10_mode_a_slug_autofill_logic_intact(self):
        assert (
            '_af_auto_slug = _contract_slug_pre or generate_slug(app.get("name", ""))'
            in _DASHBOARD_SRC
        )
        assert 'af_slug = st.text_input(' in _DASHBOARD_SRC

    def test_10b_generate_slug_function_itself_unmodified(self):
        import inspect
        from modules import slug_generator
        src = inspect.getsource(slug_generator.generate_slug)
        assert "def generate_slug(name: str) -> str:" in src


# ── 11. Tier2-B 독립성 ───────────────────────────────────────────────────────

class TestTier2BIndependence:
    def test_11_block_does_not_reference_tier2b_state(self):
        block = _contract_slug_block()
        assert "tier2b" not in block.lower()
        assert "af_contract_is_tier2b" not in block


# ── 12. Mode 추천과 독립성 ───────────────────────────────────────────────────

class TestModeRecommendationIndependence:
    def test_12_block_does_not_reference_mode_suggestion(self):
        block = _contract_slug_block()
        assert "af_mode_suggest" not in block
        assert "suggest_mode" not in block


# ── 13. legal_refs / test_cases 무관여 ───────────────────────────────────────

class TestLegalRefsTestCasesUntouched:
    def test_13_block_does_not_write_legal_refs_or_test_cases(self):
        block = _contract_slug_block()
        assert "legal_refs" not in block
        assert "test_cases" not in block
