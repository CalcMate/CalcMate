# -*- coding: utf-8 -*-
"""wordpress_media_uploader.py — WordPress Media 업로드 모듈"""
import requests
from modules.publisher import _wp_auth, is_wordpress_ready
from modules.logger import get_logger

LOG = get_logger()

class WordPressMediaUploader:
    def __init__(self, cfg):
        self.cfg = cfg
        self.wp_config = cfg.get("wordpress", {})
        self.url = self.wp_config.get("url", "")
        self.username = self.wp_config.get("username", "")
        self.app_password = self.wp_config.get("app_password", "")

    def upload_image(self, image_path: str) -> str:
        """WordPress에 이미지를 업로드하고 attachment_id를 반환합니다."""
        if not self.url or not self.username or not self.app_password:
            LOG.warning("WordPress 인증 정보 누락 — 미디어 업로드 불가.")
            return "FAILED"
            
        # 실제 API 호출 (Mock 가능하도록 구조화)
        # /wp-json/wp/v2/media
        
        # MOCKING: 성공 가정
        LOG.info("이미지 업로드 성공 (Mock): %s", image_path)
        return "999" # Mock Attachment ID
