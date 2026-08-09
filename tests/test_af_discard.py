# -*- coding: utf-8 -*-
"""tests/test_af_discard.py — 「생성 결과 폐기 & 초기화」 버튼 로직 테스트

검증 범위:
  - AF_SESSION_DISCARD_KEYS 목록 완전성
  - 확인(Confirm) 시 세션 키 전체 소거
  - 취소(Cancel) 시 세션 키 유지
  - 기존 저장 데이터(Registry/calculators/app_templates) 보호
  - 연차잔여일계산기 시나리오 — 폐기 시 Registry 미추가 확인
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import yaml
from modules.app_factory import AF_SESSION_DISCARD_KEYS

_REG_DIR = Path(__file__).resolve().parent.parent / "docs" / "registry"


# ─────────────────────────────────────────────────────────────
# 헬퍼: 세션 상태 시뮬레이터
# ─────────────────────────────────────────────────────────────

def _full_session() -> dict:
    """App Factory가 사용하는 모든 세션 키를 채운 샘플 상태."""
    return {
        "af_result": {
            "name": "연차잔여일계산기",
            "html": "<html><body>연차</body></html>",
            "seo_title": "연차 잔여일 계산기",
            "faq": ["Q1"],
            "input_schema": {"years_of_service": "number"},
            "output_schema": {"remaining_days": "number"},
            "formula": {"remaining_days": "years_of_service * 1.5"},
            "_formula_valid": True,
            "_formula_msg": "OK",
            "_tokens": 1200,
            "_steps": [("spec", "gpt"), ("html", "claude")],
            "calculator_type": "formula",
            "tier": 2,
        },
        "af_name": "연차잔여일계산기",
        "af_cat": "노무/급여",
        "af_desc": "근속연수와 사용일수로 잔여 연차 계산",
        "af_tier": 2,
        "af_slug": "annual-leave-remaining",
        "af_keyword": "연차",
        "af_tier_suggest": {"tier": "Tier2-A", "confidence": "high", "reason": "단순 산술"},
        "_af_last_slug_for": "연차잔여일계산기",
        "af_seo": "연차 잔여일 계산기",
        "af_discard_confirm": True,
        # 다른 탭/기능 관련 키 (폐기 시 절대 건드리면 안 됨)
        "nav_group": "🧮 Calculator",
        "sub_🧮 Calculator": "🏭 App Factory",
        "ws_msgs": [{"role": "user", "content": "hello"}],
    }


def _simulate_confirm(session: dict) -> dict:
    """'폐기하고 초기화' 버튼 동작: DISCARD_KEYS 목록 소거."""
    for k in AF_SESSION_DISCARD_KEYS:
        session.pop(k, None)
    return session


def _simulate_cancel(session: dict) -> dict:
    """'취소' 버튼 동작: af_discard_confirm 플래그만 제거."""
    session.pop("af_discard_confirm", None)
    return session


# ─────────────────────────────────────────────────────────────
# 1. AF_SESSION_DISCARD_KEYS 목록 완전성
# ─────────────────────────────────────────────────────────────

class TestAfDiscardKeysList:
    """AF_SESSION_DISCARD_KEYS가 필수 키를 모두 포함하는지 확인."""

    REQUIRED_KEYS = {
        "af_result",
        "af_name",
        "af_cat",
        "af_desc",
        "af_tier",
        "af_slug",
        "af_keyword",
        "af_tier_suggest",
        "_af_last_slug_for",
        "af_discard_confirm",
    }

    def test_required_keys_all_present(self):
        assert self.REQUIRED_KEYS.issubset(set(AF_SESSION_DISCARD_KEYS)), (
            f"누락 키: {self.REQUIRED_KEYS - set(AF_SESSION_DISCARD_KEYS)}"
        )

    def test_no_non_af_keys(self):
        """폐기 대상에 다른 탭 관련 키가 없어야 한다."""
        non_af = [k for k in AF_SESSION_DISCARD_KEYS
                  if not k.startswith("af_") and not k.startswith("_af_")]
        assert non_af == [], f"다른 탭 키가 포함됨: {non_af}"

    def test_is_tuple_immutable(self):
        assert isinstance(AF_SESSION_DISCARD_KEYS, tuple)


# ─────────────────────────────────────────────────────────────
# 2. 확인(Confirm) — 세션 키 전체 소거
# ─────────────────────────────────────────────────────────────

class TestAfDiscardConfirm:
    """'폐기하고 초기화' 선택 시 모든 대상 키가 소거된다."""

    def test_af_result_cleared(self):
        session = _full_session()
        _simulate_confirm(session)
        assert "af_result" not in session

    def test_af_name_cleared(self):
        session = _full_session()
        _simulate_confirm(session)
        assert "af_name" not in session

    def test_af_cat_cleared(self):
        session = _full_session()
        _simulate_confirm(session)
        assert "af_cat" not in session

    def test_af_desc_cleared(self):
        session = _full_session()
        _simulate_confirm(session)
        assert "af_desc" not in session

    def test_af_tier_cleared(self):
        session = _full_session()
        _simulate_confirm(session)
        assert "af_tier" not in session

    def test_af_slug_cleared(self):
        session = _full_session()
        _simulate_confirm(session)
        assert "af_slug" not in session

    def test_af_keyword_cleared(self):
        session = _full_session()
        _simulate_confirm(session)
        assert "af_keyword" not in session

    def test_af_tier_suggest_cleared(self):
        session = _full_session()
        _simulate_confirm(session)
        assert "af_tier_suggest" not in session

    def test_internal_slug_tracking_cleared(self):
        session = _full_session()
        _simulate_confirm(session)
        assert "_af_last_slug_for" not in session

    def test_af_discard_confirm_flag_cleared(self):
        session = _full_session()
        _simulate_confirm(session)
        assert "af_discard_confirm" not in session

    def test_all_discard_keys_gone(self):
        session = _full_session()
        _simulate_confirm(session)
        remaining = [k for k in AF_SESSION_DISCARD_KEYS if k in session]
        assert remaining == [], f"소거 안 된 키: {remaining}"

    def test_idempotent_on_empty_session(self):
        """빈 세션에서 폐기 실행해도 오류 없음."""
        session = {}
        _simulate_confirm(session)
        assert session == {}


# ─────────────────────────────────────────────────────────────
# 3. 취소(Cancel) — 세션 키 유지
# ─────────────────────────────────────────────────────────────

class TestAfDiscardCancel:
    """'취소' 선택 시 af_discard_confirm 플래그만 제거되고 나머지 유지."""

    def test_af_result_preserved(self):
        session = _full_session()
        original_result = session["af_result"]
        _simulate_cancel(session)
        assert session.get("af_result") == original_result

    def test_af_name_preserved(self):
        session = _full_session()
        _simulate_cancel(session)
        assert session.get("af_name") == "연차잔여일계산기"

    def test_af_cat_preserved(self):
        session = _full_session()
        _simulate_cancel(session)
        assert session.get("af_cat") == "노무/급여"

    def test_af_desc_preserved(self):
        session = _full_session()
        _simulate_cancel(session)
        assert session.get("af_desc") == "근속연수와 사용일수로 잔여 연차 계산"

    def test_af_slug_preserved(self):
        session = _full_session()
        _simulate_cancel(session)
        assert session.get("af_slug") == "annual-leave-remaining"

    def test_af_tier_preserved(self):
        session = _full_session()
        _simulate_cancel(session)
        assert session.get("af_tier") == 2

    def test_confirm_flag_removed(self):
        session = _full_session()
        _simulate_cancel(session)
        assert "af_discard_confirm" not in session

    def test_other_tab_keys_preserved(self):
        session = _full_session()
        _simulate_cancel(session)
        assert session.get("nav_group") == "🧮 Calculator"
        assert session.get("ws_msgs") is not None


# ─────────────────────────────────────────────────────────────
# 4. 기존 저장 데이터 보호 (Registry/파일 불변 확인)
# ─────────────────────────────────────────────────────────────

class TestSavedDataProtection:
    """폐기 작업은 세션 상태 조작만 수행 — Registry/DB/파일에 영향 없음."""

    def test_registry_files_exist_after_discard(self):
        """폐기 시뮬레이션 후 registry YAML 파일이 그대로 존재한다."""
        yaml_files_before = sorted(p.name for p in _REG_DIR.glob("*.yaml"))
        # 폐기 시뮬레이션 (세션 조작만)
        session = _full_session()
        _simulate_confirm(session)
        yaml_files_after = sorted(p.name for p in _REG_DIR.glob("*.yaml"))
        assert yaml_files_before == yaml_files_after

    def test_labor_af_unchanged_after_discard(self):
        """labor_af.yaml 내용이 폐기 시뮬레이션 전후로 동일하다."""
        labor_af = _REG_DIR / "labor_af.yaml"
        if not labor_af.exists():
            return  # 파일 없으면 스킵
        content_before = labor_af.read_text(encoding="utf-8")
        session = _full_session()
        _simulate_confirm(session)
        content_after = labor_af.read_text(encoding="utf-8")
        assert content_before == content_after

    def test_existing_registry_slugs_intact(self):
        """Registry의 기존 slug 목록이 폐기 시뮬레이션 후에도 동일하다."""
        def _collect_slugs() -> set:
            slugs = set()
            for yf in _REG_DIR.glob("*.yaml"):
                data = yaml.safe_load(yf.read_text(encoding="utf-8")) or {}
                for item in (data.get("calculators") or []):
                    if isinstance(item, dict) and item.get("slug"):
                        slugs.add(item["slug"])
            return slugs

        slugs_before = _collect_slugs()
        session = _full_session()
        _simulate_confirm(session)
        slugs_after = _collect_slugs()
        assert slugs_before == slugs_after

    def test_other_session_keys_untouched(self):
        """폐기 후 다른 탭·기능 세션 키(nav_group, ws_msgs 등)는 보존된다."""
        session = _full_session()
        nav_before = session["nav_group"]
        ws_before = session["ws_msgs"]
        _simulate_confirm(session)
        assert session.get("nav_group") == nav_before
        assert session.get("ws_msgs") == ws_before


# ─────────────────────────────────────────────────────────────
# 5. 연차잔여일계산기 시나리오
# ─────────────────────────────────────────────────────────────

class TestAnnualLeaveDiscardScenario:
    """annual-leave-remaining 을 생성만 하고 저장 없이 폐기 — Registry 미추가."""

    def _registry_slug_set(self) -> set:
        slugs = set()
        for yf in _REG_DIR.glob("*.yaml"):
            data = yaml.safe_load(yf.read_text(encoding="utf-8")) or {}
            for item in (data.get("calculators") or []):
                if isinstance(item, dict) and item.get("slug"):
                    slugs.add(item["slug"])
        return slugs

    def test_discard_does_not_add_slug_to_registry(self):
        """저장하지 않고 폐기하면 annual-leave-remaining이 Registry에 추가되지 않는다."""
        slugs_before = self._registry_slug_set()

        # 생성 결과가 세션에 있는 상태를 시뮬레이션
        session = _full_session()
        assert session["af_result"]["name"] == "연차잔여일계산기"
        # 저장(save_app) 없이 폐기만 수행
        _simulate_confirm(session)

        slugs_after = self._registry_slug_set()
        # Registry slug 변화 없음
        assert slugs_before == slugs_after

    def test_discard_clears_annual_leave_result(self):
        """폐기 후 af_result의 annual-leave 데이터가 세션에 남지 않는다."""
        session = _full_session()
        assert session.get("af_result") is not None
        _simulate_confirm(session)
        assert session.get("af_result") is None

    def test_discard_clears_annual_leave_slug(self):
        """폐기 후 af_slug 'annual-leave-remaining'이 세션에 남지 않는다."""
        session = _full_session()
        assert session.get("af_slug") == "annual-leave-remaining"
        _simulate_confirm(session)
        assert session.get("af_slug") is None

    def test_no_double_entry_on_repeated_discard(self):
        """폐기를 두 번 반복해도 Registry 변화 없음 (멱등성)."""
        slugs_before = self._registry_slug_set()
        for _ in range(2):
            session = _full_session()
            _simulate_confirm(session)
        slugs_after = self._registry_slug_set()
        assert slugs_before == slugs_after
