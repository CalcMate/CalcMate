# -*- coding: utf-8 -*-
"""tests/media_pipeline_test.py — 미디어 파이프라인 통합 테스트"""
import pytest
from content_pipeline.image_builder import ImageBuilder
from content_pipeline.wordpress_media_uploader import WordPressMediaUploader
from modules.config_loader import load_config
from unittest.mock import MagicMock

def test_image_builder():
    builder = ImageBuilder()
    result = builder.build_images("<h2>계산방법</h2><p>p1</p><p>p2</p>", "주휴수당", "weekly-holiday-allowance")
    assert "<!-- wp:image -->" in result
    assert "주휴수당 계산방법" in result

def test_media_uploader():
    uploader = WordPressMediaUploader(load_config())
    # Mock upload call to avoid actual API dependency
    uploader.upload_image = MagicMock(return_value="999")
    attachment_id = uploader.upload_image("test.png")
    assert attachment_id == "999"
    uploader.upload_image.assert_called_once()
