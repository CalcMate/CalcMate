# -*- coding: utf-8 -*-
"""
tests/test_html_normalization.py — Markdown/pre 정규화 재발 방지 테스트

콘텐츠 렌더링 이슈 재발 방지 수정(modules/cleaner.py: normalize_bold_markdown,
normalize_pre_blocks, normalize_html_output)의 deterministic 동작을 검증한다.
"""
from modules import cleaner


# ── Case A~D: Markdown bold → <strong> ──

def test_case_a_plain_markdown_bold_converts():
    assert cleaner.normalize_bold_markdown("**국민연금**") == "<strong>국민연금</strong>"


def test_case_b_existing_strong_untouched():
    html = "<strong>국민연금</strong>"
    assert cleaner.normalize_bold_markdown(html) == html


def test_case_c_mixed_html_only_markdown_converts():
    html = "<p>안내: <strong>국민연금</strong>과 **건강보험**입니다.</p>"
    expected = "<p>안내: <strong>국민연금</strong>과 <strong>건강보험</strong>입니다.</p>"
    assert cleaner.normalize_bold_markdown(html) == expected


def test_case_d_multiple_bold_markers_all_convert():
    html = "**A**와 **B**를 확인하세요."
    expected = "<strong>A</strong>와 <strong>B</strong>를 확인하세요."
    assert cleaner.normalize_bold_markdown(html) == expected


def test_case_e_structure_preserved_around_bold():
    html = (
        "<h2>지급 대상</h2><p>**국민연금**은 필수입니다.</p>"
        "<ul><li>항목 1</li><li>**항목 2**</li></ul>"
    )
    result = cleaner.normalize_bold_markdown(html)
    assert "<h2>지급 대상</h2>" in result
    assert "<ul><li>항목 1</li><li><strong>항목 2</strong></li></ul>" in result
    assert "**" not in result


def test_no_bold_markers_returns_unchanged():
    html = "<p>일반 문단입니다.</p>"
    assert cleaner.normalize_bold_markdown(html) == html


def test_empty_string_safe():
    assert cleaner.normalize_bold_markdown("") == ""


# ── <pre> 정규화: 일반 계산식은 <p>로, 코드성 블록은 유지 ──

def test_pre_formula_converts_to_paragraphs():
    html = "<pre>주휴수당 = 시급 × (주간 근무 시간 ÷ 40) × 8\n주휴수당 = 10,000원 × (40 ÷ 40) × 8 = 80,000원\n</pre>"
    result = cleaner.normalize_pre_blocks(html)
    assert "<pre" not in result
    assert "<p>주휴수당 = 시급 × (주간 근무 시간 ÷ 40) × 8</p>" in result
    assert "<p>주휴수당 = 10,000원 × (40 ÷ 40) × 8 = 80,000원</p>" in result


def test_pre_with_code_marker_is_preserved():
    html = "<pre>function calc() {\n  return a + b;\n}</pre>"
    result = cleaner.normalize_pre_blocks(html)
    assert result == html


def test_pre_with_semicolon_marker_preserved():
    html = "<pre>SELECT * FROM calculators;</pre>"
    result = cleaner.normalize_pre_blocks(html)
    assert "<pre" in result


def test_pre_no_tag_returns_unchanged():
    html = "<p>내용에 pre가 없습니다.</p>"
    assert cleaner.normalize_pre_blocks(html) == html


def test_pre_empty_block_unchanged():
    html = "<pre></pre>"
    assert cleaner.normalize_pre_blocks(html) == html


# ── 통합: normalize_html_output ──

def test_normalize_html_output_handles_both_issues():
    html = (
        "<h2>계산 방법</h2><p>1. **국민연금**: 4.5% 공제</p>"
        "<pre>주휴수당 = 시급 × (주간 근무 시간 ÷ 40) × 8</pre>"
    )
    result = cleaner.normalize_html_output(html)
    assert "**" not in result
    assert "<strong>국민연금</strong>" in result
    assert "<pre" not in result
    assert "<p>주휴수당 = 시급 × (주간 근무 시간 ÷ 40) × 8</p>" in result


def test_normalize_html_output_idempotent_on_clean_html():
    html = "<h2>제목</h2><p><strong>강조</strong>된 정상 HTML입니다.</p>"
    assert cleaner.normalize_html_output(html) == html


def test_normalize_html_output_empty_safe():
    assert cleaner.normalize_html_output("") == ""
    assert cleaner.normalize_html_output(None) is None
