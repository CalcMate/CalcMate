# -*- coding: utf-8 -*-
"""
tests/test_static_publisher.py — Static Publisher MVP 검증 (STEP 2)

검증:
1. Content Schema — 10건 모두 필수 필드 보유
2. URL — 모든 블로그 URL이 /blog/{slug}/
3. HTML 생성 — title/description/canonical/H1/본문 존재
4. HTML preservation — article_content의 h2/p/strong이 Markdown으로 변환되지 않음
5. 이미지 범위 — image=None이면 <img>/og:image 미생성
6. sitemap — 10건 /blog/{slug}/ URL 포함
7. 기존 계산기 페이지 보호 — /{slug}/index.html 무변경
8. 기존 WordPress Publisher 보호 — WP 관련 개념을 참조하지 않음(구조적 검증)
"""
import hashlib
import inspect
import sys
import os

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from content.blog import GOLDEN_10

GOLDEN10_SLUGS = [gc.slug for gc in GOLDEN_10]


def _sample_article_html(slug: str) -> str:
    """실제 DB article_content와 동일한 형태(h2/p/strong)의 테스트 전용 본문."""
    return (
        f"<h2>지급 대상</h2><p>{slug} 관련 <strong>테스트 본문</strong>입니다. "
        f"실제 법령 문구가 아니라 Static Publisher 검증용 더미 콘텐츠입니다.</p>"
        f"<h2>계산 방법</h2><p>테스트 계산 방법 설명입니다.</p>"
    )


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def fake_calc_rows():
    """실제 calculators 테이블 스키마(category/generated_at/created_at 포함)를
    흉내낸 테스트 전용 데이터. 실 DB나 gitignored 파일에 의존하지 않는다."""
    rows = {}
    for i, gc in enumerate(GOLDEN_10):
        rows[gc.slug] = {
            "slug": gc.slug,
            "name": f"{gc.slug} 계산기",
            "category": "노무/급여" if i % 2 == 0 else "고용/보험",
            "article_content": _sample_article_html(gc.slug),
            "seo_title": "",
            "seo_description": "",
            "seo_desc": "",
            "generated_at": f"2026-08-{10 + i:02d}T00:00:00",
            "created_at": f"2026-08-{1 + i:02d}T00:00:00",
        }
    return rows


@pytest.fixture
def load_calculator_fn(fake_calc_rows):
    def _load(cfg, slug):
        return fake_calc_rows.get(slug)
    return _load


@pytest.fixture
def cfg():
    return {
        "SITE_URL": "https://calcmate.kr",
        "SITE_NAME": "CalcMate",
        "GA4_MEASUREMENT_ID": "G-TEST123",
    }


@pytest.fixture
def content_results(cfg, load_calculator_fn):
    from modules.blog_content_assembler import assemble_all_golden10
    return assemble_all_golden10(cfg, load_calculator_fn=load_calculator_fn)


# ============================================================
# Test 1: Content Schema
# ============================================================

class TestContentSchema:
    REQUIRED_FIELDS = ["title", "slug", "description", "date", "category",
                       "content", "canonical"]

    def test_10_results_produced(self, content_results):
        assert len(content_results) == 10

    def test_all_required_fields_present_and_nonempty(self, content_results):
        for r in content_results:
            for field in self.REQUIRED_FIELDS:
                assert field in r, f"{r.get('slug')}: '{field}' 필드 없음"
                assert r[field], f"{r.get('slug')}.{field} 비어있음"

    def test_slugs_match_golden10_exactly(self, content_results):
        assert {r["slug"] for r in content_results} == set(GOLDEN10_SLUGS)

    def test_title_prefers_golden10_contract(self, content_results):
        by_slug = {r["slug"]: r for r in content_results}
        for gc in GOLDEN_10:
            assert by_slug[gc.slug]["title"] == gc.title

    def test_description_prefers_golden10_contract(self, content_results):
        by_slug = {r["slug"]: r for r in content_results}
        for gc in GOLDEN_10:
            assert by_slug[gc.slug]["description"] == gc.description

    def test_content_matches_db_article_content_verbatim(self, content_results, fake_calc_rows):
        for r in content_results:
            assert r["content"] == fake_calc_rows[r["slug"]]["article_content"]

    def test_image_is_none(self, content_results):
        for r in content_results:
            assert r["image"] is None

    def test_mismatched_slug_raises_not_silently_fixed(self, cfg):
        from modules.blog_content_assembler import assemble_content_result, ContentAssemblyError
        bad_calc = {"slug": "not-in-golden10", "article_content": "<p>x</p>"}
        with pytest.raises(ContentAssemblyError):
            assemble_content_result(bad_calc, cfg)

    def test_missing_slug_in_db_raises(self, cfg):
        from modules.blog_content_assembler import assemble_all_golden10, ContentAssemblyError

        def _load_missing_one(cfg, slug):
            if slug == GOLDEN10_SLUGS[0]:
                return None
            return {"slug": slug, "article_content": "<p>x</p>"}

        with pytest.raises(ContentAssemblyError):
            assemble_all_golden10(cfg, load_calculator_fn=_load_missing_one)


# ============================================================
# Test 2: URL
# ============================================================

class TestURL:
    def test_output_path_is_blog_prefixed(self, tmp_path):
        from modules.static_publisher import blog_output_path
        for slug in GOLDEN10_SLUGS:
            p = blog_output_path(tmp_path, slug)
            rel = str(p.relative_to(tmp_path)).replace("\\", "/")
            assert rel == f"blog/{slug}/index.html"

    def test_canonical_uses_blog_prefix(self, content_results):
        for r in content_results:
            assert r["canonical"] == f"https://calcmate.kr/blog/{r['slug']}/"


# ============================================================
# Test 3: HTML 생성
# ============================================================

class TestHTMLGeneration:
    def test_html_contains_required_elements(self, content_results, cfg):
        from modules.site_generator import _blog_page
        import html as _html

        for r in content_results:
            page = _blog_page(r, cfg)
            assert f"<title>{_html.escape(r['title'])}</title>" in page
            assert f'name="description" content="{_html.escape(r["description"])}"' in page
            assert f'<link rel="canonical" href="{_html.escape(r["canonical"])}">' in page
            assert f'og:title" content="{_html.escape(r["title"])}"' in page
            assert f'og:description" content="{_html.escape(r["description"])}"' in page
            assert f'og:url" content="{_html.escape(r["canonical"])}"' in page
            assert "<h1" in page
            assert _html.escape(r["title"]) in page
            assert r["content"] in page  # 본문은 그대로 삽입(가공 없음)


# ============================================================
# Test 4: HTML preservation (Markdown 변환 없음)
# ============================================================

class TestHTMLPreservation:
    def test_html_tags_not_converted_to_markdown(self, content_results, cfg):
        from modules.site_generator import _blog_page
        for r in content_results:
            page = _blog_page(r, cfg)
            assert "<h2>" in page
            assert "<p>" in page
            assert "<strong>" in page
            assert "##" not in page
            assert "**" not in page


# ============================================================
# Test 5: 이미지 범위
# ============================================================

class TestImageScope:
    def test_no_img_tag_or_og_image_when_none(self, content_results, cfg):
        from modules.site_generator import _blog_page
        for r in content_results:
            assert r["image"] is None
            page = _blog_page(r, cfg)
            assert "<img" not in page
            assert "og:image" not in page


# ============================================================
# Test 6: sitemap
# ============================================================

class TestSitemap:
    def test_sitemap_includes_all_10_blog_urls(self, cfg):
        from modules.site_generator import generate_sitemap
        xml = generate_sitemap(cfg)
        for slug in GOLDEN10_SLUGS:
            assert f"<loc>{cfg['SITE_URL']}/blog/{slug}/</loc>" in xml


# ============================================================
# Test 7: 기존 계산기 페이지 보호
# ============================================================

class TestExistingCalculatorPageProtection:
    def test_existing_calculator_page_untouched_after_publish(self, tmp_path, content_results, cfg):
        site_dir = tmp_path / "_site"
        calc_page = site_dir / "severance-pay" / "index.html"
        calc_page.parent.mkdir(parents=True)
        calc_page.write_text("<html>EXISTING CALCULATOR PAGE — DO NOT TOUCH</html>", encoding="utf-8")
        before_hash = hashlib.sha256(calc_page.read_bytes()).hexdigest()

        from modules.static_publisher import publish_all
        publish_all(content_results, cfg, site_dir=site_dir)

        after_hash = hashlib.sha256(calc_page.read_bytes()).hexdigest()
        assert before_hash == after_hash, "기존 계산기 페이지가 변경됨 — 절대 금지"

        # 블로그는 별도 경로에 생성됨
        assert (site_dir / "blog" / "severance-pay" / "index.html").exists()
        # 계산기 페이지 디렉토리에는 블로그 파일이 섞이지 않음
        assert list(calc_page.parent.iterdir()) == [calc_page]

    def test_publish_creates_exactly_10_blog_pages(self, tmp_path, content_results, cfg):
        from modules.static_publisher import publish_all
        site_dir = tmp_path / "_site"
        paths = publish_all(content_results, cfg, site_dir=site_dir)
        assert len(paths) == 10
        for p in paths:
            assert p.exists()
            assert "/blog/" in str(p).replace("\\", "/")


# ============================================================
# Test 8: 기존 WordPress Publisher 보호(구조적 검증)
# ============================================================

class TestWordPressPublisherUntouched:
    """실제 fallback 동작 검증은 tests/test_publisher_seo_description_fallback.py가
    담당한다(STEP 2-N에서 별도 실행). 여기서는 static_publisher.py가 애초에
    WP 관련 개념을 참조조차 하지 않음을 구조적으로 확인한다."""

    def test_static_publisher_module_has_no_wp_references(self):
        import modules.static_publisher as SP
        src = inspect.getsource(SP)
        forbidden = ["modules.publisher", "wp_post_id", "wp_permalink",
                     "featured_media", "WORDPRESS_", "run_blog_once_wp"]
        for token in forbidden:
            assert token not in src, f"static_publisher.py에 WP 관련 참조 발견: {token}"

    def test_blog_content_assembler_has_no_wp_references(self):
        import modules.blog_content_assembler as BCA
        src = inspect.getsource(BCA)
        forbidden = ["modules.publisher", "wp_post_id", "featured_media", "WORDPRESS_"]
        for token in forbidden:
            assert token not in src, f"blog_content_assembler.py에 WP 관련 참조 발견: {token}"

    def test_publisher_module_unaffected_by_import(self):
        """static_publisher를 import해도 publisher.py의 공개 인터페이스가 그대로임을 확인."""
        import modules.publisher as publisher
        import modules.static_publisher  # noqa: F401
        assert hasattr(publisher, "publish")
        assert hasattr(publisher, "update_post")
