# -*- coding: utf-8 -*-
"""tests/test_phase5e_wp_image_preserve.py — Phase 5-E MINOR-1/2 회귀 테스트

MINOR-1: wp:image 블록의 alt 텍스트가 request JSON의 images.body.alt로 전달되는가
MINOR-2: _phase5e_wp_update.py 재실행 시 기존 wp:image 블록이 유실/중복되지 않는가

실제 WordPress 호출 없이 순수 함수(extract_image_blocks / set_img_alt /
merge_image_blocks)만 검증한다.
"""
import re

import pytest

from scripts._phase5e_wp_update import (
    extract_image_blocks,
    merge_image_blocks,
    set_img_alt,
)


def _nblocks(content: str) -> int:
    return len(re.findall(r"<!--\s*wp:image\b", content))


SAMPLE_BLOCK = (
    '<!-- wp:image {"sizeSlug":"full"} -->\n'
    '<figure class="wp-block-image size-full">'
    '<img src="http://x.test/img1.webp" alt="" /></figure>\n'
    '<!-- /wp:image -->'
)

OLD_CONTENT = (
    "<!-- wp:html -->\n<h2>지급 조건</h2>\n<p>본문 텍스트</p>\n<!-- /wp:html -->\n\n"
    + SAMPLE_BLOCK
)


class TestExtractImageBlocks:
    def test_추출_및_직전_H2_앵커(self):
        blocks = extract_image_blocks(OLD_CONTENT)
        assert len(blocks) == 1
        block, anchor = blocks[0]
        assert "wp:image" in block
        assert anchor == "지급 조건"

    def test_이미지_없는_content는_빈_리스트(self):
        assert extract_image_blocks("<h2>제목</h2><p>본문</p>") == []


class TestSetImgAlt:
    def test_빈_alt는_그대로(self):
        assert set_img_alt('<img src="a" alt=""/>', "") == '<img src="a" alt=""/>'

    def test_alt_전달(self):
        out = set_img_alt('<img src="a" alt=""/>', "설명 이미지")
        assert 'alt="설명 이미지"' in out

    def test_기존_alt_교체(self):
        out = set_img_alt('<img src="a" alt="기존"/>', "새 설명")
        assert 'alt="새 설명"' in out
        assert "기존" not in out


class TestMergeImageBlocks:
    def test_기존_이미지_보존_및_H2_직후_위치(self):
        new_body = "<h2>지급 조건</h2>\n<p>새 본문</p>\n<h2>FAQ</h2>\n<p>질문</p>"
        merged = merge_image_blocks(new_body, extract_image_blocks(OLD_CONTENT), alt="4대보험 설명 이미지")
        assert _nblocks(merged) == 1
        assert 'alt="4대보험 설명 이미지"' in merged
        assert "<h2>지급 조건</h2>\n\n<!-- wp:image" in merged

    def test_중복_방지_동일_src(self):
        # 새 본문에 이미 동일 src의 wp:image 블록이 존재 → 1개로 유지
        new_body = (
            "<h2>지급 조건</h2>\n<p>본문</p>\n"
            + SAMPLE_BLOCK
        )
        merged = merge_image_blocks(new_body, extract_image_blocks(OLD_CONTENT), alt="새 alt")
        assert _nblocks(merged) == 1

    def test_이미지_없는_글은_그대로(self):
        body = "<h2>제목</h2><p>본문</p>"
        assert merge_image_blocks(body, [], alt="x") == body

    def test_H2_앵커_불일치시_끝에_추가(self):
        blocks = [(SAMPLE_BLOCK, "존재하지 않는 H2")]
        merged = merge_image_blocks("<h2>FAQ</h2><p>본문</p>", blocks, alt="a")
        assert _nblocks(merged) == 1
        assert merged.endswith("<!-- /wp:image -->")
