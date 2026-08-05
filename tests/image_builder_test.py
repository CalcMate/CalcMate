# -*- coding: utf-8 -*-
"""tests/image_builder_test.py — InlineImageBuilder 테스트"""
import pytest
from content_pipeline.image_builder import ImageBuilder

@pytest.fixture
def builder():
    return ImageBuilder()

def test_build_images_success(builder):
    """문단 2개 이상인 섹션에 이미지 삽입"""
    content = "<h2>계산방법</h2><p>p1</p><p>p2</p><h2>계산예시</h2><p>p1</p><p>p2</p>"
    result = builder.build_images(content, "주휴수당", "weekly-holiday-allowance")
    
    assert "<!-- wp:image -->" in result
    assert result.count("<!-- wp:image -->") == 2 # 2개 섹션 삽입

def test_build_images_skip_insufficient_paragraphs(builder):
    """문단 1개인 섹션은 이미지 삽입 건너뜀"""
    content = "<h2>계산방법</h2><p>p1</p><h2>계산예시</h2><p>p1</p>"
    result = builder.build_images(content, "주휴수당", "weekly-holiday-allowance")
    
    assert "<!-- wp:image -->" not in result

def test_build_images_idempotent(builder):
    """재실행 시 중복 삽입 방지"""
    content = "<h2>계산방법</h2><p>p1</p><p>p2</p>"
    # 1차 실행
    res1 = builder.build_images(content, "주휴수당", "weekly-holiday-allowance")
    # 2차 실행
    res2 = builder.build_images(res1, "주휴수당", "weekly-holiday-allowance")
    
    assert res1.count("<!-- wp:image -->") == 1
    assert res2.count("<!-- wp:image -->") == 1

def test_wordpress_block_format(builder):
    """WordPress Image Block 형식 검증"""
    content = "<h2>계산방법</h2><p>p1</p><p>p2</p>"
    result = builder.build_images(content, "주휴수당", "weekly-holiday-allowance")
    
    expected_block = (
        "\n\n<!-- wp:image -->\n"
        '<figure class="wp-block-image">\n'
        '<img src="https://placeholder.invalid/inline-image-method.webp" alt="주휴수당 계산방법">\n'
        '</figure>\n'
        "<!-- /wp:image -->\n\n"
    )
    assert expected_block in result
