# -*- coding: utf-8 -*-
"""
CTA 빌더 + 카테고리 매핑 단위 테스트
"""
import pytest
from modules.cta_builder import (
    build_cta_block,
    build_internal_links_block,
    inject_cta_and_links,
    validate_calc_url_structure,
)


class TestBuildCtaBlock:

    def test_contains_h2_marker(self):
        """G6 gate 기준: <h2>계산기 사용하기</h2> 포함."""
        html = build_cta_block("severance-pay", "퇴직금 계산기")
        assert "<h2>계산기 사용하기</h2>" in html

    def test_contains_slug_url(self):
        """calcmate.kr/slug/ 형식 URL 포함."""
        html = build_cta_block("severance-pay", "퇴직금 계산기")
        assert "https://calcmate.kr/severance-pay/" in html

    def test_contains_calc_name(self):
        """계산기 이름이 본문에 포함."""
        html = build_cta_block("weekly-holiday-allowance", "주휴수당 계산기")
        assert "주휴수당 계산기" in html

    def test_custom_site_url(self):
        """site_url 커스텀 사용."""
        html = build_cta_block("severance-pay", "계산기", site_url="https://example.com")
        assert "https://example.com/severance-pay/" in html

    def test_contains_anchor_tag(self):
        """<a href> 링크 포함."""
        html = build_cta_block("severance-pay", "퇴직금 계산기")
        assert '<a href=' in html


class TestBuildInternalLinksBlock:

    def test_known_slug_has_links(self):
        """registered slug → related links 생성."""
        html = build_internal_links_block("severance-pay")
        assert '<div class="internal-links">' in html
        assert "<li>" in html

    def test_max_links_respected(self):
        """max_links 제한 준수."""
        html = build_internal_links_block("severance-pay", max_links=2)
        li_count = html.count("<li>")
        assert li_count <= 2

    def test_unknown_slug_empty(self):
        """master YAML에 없는 slug → 빈 문자열."""
        html = build_internal_links_block("nonexistent-calc")
        assert html == ""

    def test_links_contain_site_url(self):
        """생성된 링크가 site_url을 사용."""
        html = build_internal_links_block("severance-pay", site_url="https://test.example")
        assert "https://test.example/" in html


class TestInjectCtaAndLinks:

    def test_no_cta_inserts(self):
        """CTA 없는 본문 → CTA 삽입."""
        body = "<h2>FAQ</h2><p>내용.</p>"
        result, report = inject_cta_and_links(body, "severance-pay", "퇴직금 계산기")
        assert "<h2>계산기 사용하기</h2>" in result
        assert report["cta_inserted"] is True

    def test_existing_cta_skipped(self):
        """이미 CTA 있으면 재삽입 안 함."""
        body = "<h2>계산기 사용하기</h2><p>기존 CTA.</p>"
        result, report = inject_cta_and_links(body, "severance-pay", "퇴직금 계산기")
        assert report["cta_inserted"] is False
        assert result.count("<h2>계산기 사용하기</h2>") == 1

    def test_internal_links_inserted(self):
        """내부링크 블록 삽입."""
        body = "<h2>FAQ</h2><p>내용.</p>"
        result, report = inject_cta_and_links(body, "severance-pay", "퇴직금 계산기")
        assert '<div class="internal-links">' in result
        assert report["links_inserted"] is True
        assert report["internal_links_count"] > 0

    def test_existing_links_skipped(self):
        """이미 internal-links 있으면 재삽입 안 함."""
        body = '<div class="internal-links"><ul><li>기존</li></ul></div>'
        result, report = inject_cta_and_links(body, "severance-pay", "퇴직금 계산기")
        assert report["links_inserted"] is False

    def test_url_in_injected_cta(self):
        """삽입된 CTA에 올바른 URL 포함."""
        body = "<p>본문.</p>"
        result, _ = inject_cta_and_links(body, "four-insurances", "4대보험 계산기")
        assert "https://calcmate.kr/four-insurances/" in result


class TestValidateCalcUrlStructure:

    def test_known_slug_valid(self):
        """master YAML에 있는 slug → valid=True."""
        r = validate_calc_url_structure("severance-pay")
        assert r["valid"] is True
        assert r["known"] is True
        assert "severance-pay" in r["url"]

    def test_unknown_slug_invalid(self):
        """없는 slug → valid=False."""
        r = validate_calc_url_structure("fake-calculator")
        assert r["valid"] is False
        assert r["known"] is False

    def test_url_format(self):
        """URL 형식 검증: site_url/slug/ 패턴."""
        r = validate_calc_url_structure("weekly-holiday-allowance")
        assert r["url"] == "https://calcmate.kr/weekly-holiday-allowance/"
