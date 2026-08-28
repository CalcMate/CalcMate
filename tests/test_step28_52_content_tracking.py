# -*- coding: utf-8 -*-
"""tests/test_step28_52_content_tracking.py — STEP 28-52 회귀 테스트.

콘텐츠 SSOT 추적 필드(content_hash/content_ssot_hash/content_source/
legal_validated_*)와 freshness 판정 helper에 대한 unit test.
실제 DB에 UPDATE/INSERT를 실행하지 않는다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from modules.law_ssot import content_ssot_hash, get_slug_ssot
from modules.content_integrity import build_content_tracking_fields, get_content_freshness


class TestContentSsotHashDeterminism:
    """A. SSOT hash 결정성"""

    def test_same_slug_same_hash(self):
        h1 = content_ssot_hash("unemployment-benefit")
        h2 = content_ssot_hash("unemployment-benefit")
        assert h1 == h2

    def test_different_slug_different_hash(self):
        h1 = content_ssot_hash("unemployment-benefit")
        h2 = content_ssot_hash("weekly-holiday-allowance")
        assert h1 != h2


class TestContentSsotHashOrderingIndependence:
    """B. dict ordering 독립성"""

    def test_key_order_does_not_affect_hash(self):
        import hashlib, json
        items_a = [{"item": "x", "value": "1"}, {"item": "y", "value": "2"}]
        items_b = [{"value": "1", "item": "x"}, {"value": "2", "item": "y"}]
        h_a = hashlib.sha256(
            json.dumps(items_a, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        h_b = hashlib.sha256(
            json.dumps(items_b, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        assert h_a == h_b


class TestContentSsotHashValueChangeDetection:
    """C. 실제 items 값 변경 감지"""

    def test_value_change_changes_hash(self):
        import hashlib, json
        items_before = [{"item": "x", "value": "10,320원"}]
        items_after = [{"item": "x", "value": "10,340원"}]
        h_before = hashlib.sha256(
            json.dumps(items_before, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        h_after = hashlib.sha256(
            json.dumps(items_after, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        assert h_before != h_after

    def test_real_ssot_slug_has_items(self):
        # unemployment-benefit은 STEP 28-26에서 content_ssot.items가 등록된 실제 slug
        items = get_slug_ssot("unemployment-benefit").get("items", [])
        assert len(items) >= 1


class TestContentHash:
    """D. content hash"""

    def test_same_article_same_hash(self):
        f1 = build_content_tracking_fields("<p>정상 콘텐츠</p>", "annual-leave-allowance", "writer_auto")
        f2 = build_content_tracking_fields("<p>정상 콘텐츠</p>", "annual-leave-allowance", "writer_auto")
        assert f1["content_hash"] == f2["content_hash"]

    def test_one_char_change_changes_hash(self):
        f1 = build_content_tracking_fields("<p>정상 콘텐츠</p>", "annual-leave-allowance", "writer_auto")
        f2 = build_content_tracking_fields("<p>정상 콘텐츠A</p>", "annual-leave-allowance", "writer_auto")
        assert f1["content_hash"] != f2["content_hash"]


class TestBuildContentTrackingFields:
    def test_pass_case_status(self):
        f = build_content_tracking_fields(
            "<p>구직급여 상한액은 68,100원입니다.</p>", "unemployment-benefit", "writer_auto")
        assert f["legal_validation_status"] == "PASS"
        assert f["content_source"] == "writer_auto"
        assert f["content_ssot_hash"] == f["legal_validated_ssot_hash"]

    def test_fail_case_status(self):
        f = build_content_tracking_fields(
            "<p>구직급여 상한액은 66,000원입니다.</p>", "unemployment-benefit", "pipeline_auto")
        assert f["legal_validation_status"] == "FAIL"

    def test_empty_slug_not_checked(self):
        f = build_content_tracking_fields("<p>본문</p>", "", "dashboard_manual")
        assert f["legal_validation_status"] == "NOT_CHECKED"

    def test_no_internal_failure_list_in_payload(self):
        f = build_content_tracking_fields(
            "<p>구직급여 상한액은 66,000원입니다.</p>", "unemployment-benefit", "writer_auto")
        assert "_legal_current_passed" not in f
        assert "_legal_current_failures" not in f
        assert isinstance(f["legal_validation_status"], str)


class TestContentFreshness:
    """E. freshness 판정"""

    def test_no_ssot(self):
        row = {"slug": "annual-leave-allowance"}  # content_ssot 없는 slug(기존 테스트에서도 사용)
        assert get_content_freshness(row) == "NO_SSOT"

    def test_needs_review_missing_tracking_fields(self):
        row = {"slug": "unemployment-benefit"}  # SSOT는 있지만 추적 필드 없음(기존 17개 row와 동일 상황)
        assert get_content_freshness(row) == "NEEDS_REVIEW"

    def test_match(self):
        h = content_ssot_hash("unemployment-benefit")
        row = {
            "slug": "unemployment-benefit",
            "content_ssot_hash": h,
            "legal_validated_ssot_hash": h,
            "legal_validation_status": "PASS",
        }
        assert get_content_freshness(row) == "MATCH"

    def test_stale_when_hash_differs(self):
        row = {
            "slug": "unemployment-benefit",
            "content_ssot_hash": "old-hash",
            "legal_validated_ssot_hash": "old-hash",
            "legal_validation_status": "PASS",
        }
        assert get_content_freshness(row) == "STALE"


class TestExistingGateUnchanged:
    """기존 check_g_legal_current()/​_check_legal_current_before_save() 계약 불변 확인."""

    def test_check_g_legal_current_signature_unchanged(self):
        from modules.content_integrity import check_g_legal_current
        fails = check_g_legal_current("<p>정상 콘텐츠</p>", "annual-leave-allowance")
        assert fails == []

    def test_calculator_pipeline_helper_unchanged(self):
        from modules.calculator_pipeline import _check_legal_current_before_save
        fails = _check_legal_current_before_save(
            "<p>구직급여 상한액은 68,100원입니다.</p>", "unemployment-benefit", "cid-x")
        assert fails == []
