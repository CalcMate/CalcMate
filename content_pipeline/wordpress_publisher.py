# -*- coding: utf-8 -*-
"""wordpress_publisher.py — WordPress Draft 생성 (설정 분리)"""
import os
import requests
from modules.publisher import is_wordpress_ready
from modules.logger import get_logger

LOG = get_logger()

class WordPressPublisher:
    def __init__(self, cfg):
        self.cfg = cfg
        # ENV > config > default 우선순위
        self.wp_config = cfg.get("wordpress", {})
        self.url = os.environ.get("WP_URL", self.wp_config.get("url", ""))
        self.username = os.environ.get("WP_USERNAME", self.wp_config.get("username", ""))
        self.app_password = os.environ.get("WP_APP_PASSWORD", self.wp_config.get("app_password", ""))

    def create_draft(self, metadata: dict) -> str:
        """WordPress에 Draft(초안) 상태로 글을 생성합니다."""
        if not self.url or not self.username or not self.app_password:
            LOG.warning("WordPress 인증 정보 누락 — 초안을 생성할 수 없습니다.")
            return "FAILED"
            
        endpoint = self.url.rstrip("/") + "/wp-json/wp/v2/posts"
        
        # 메타데이터를 사용하여 페이로드 구성
        payload = {
            "title": metadata.get("title"),
            "status": "draft",
            "content": metadata.get("content"),
            "excerpt": metadata.get("excerpt"),
        }
        
        if "featured_media" in metadata:
            payload["featured_media"] = metadata["featured_media"]
        
        try:
            resp = requests.post(
                endpoint, json=payload,
                auth=(self.username, self.app_password),
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            post_id = str(data.get("id"))
            LOG.info("Draft 생성 성공 (ID: %s)", post_id)
            return post_id
        except Exception as e:
            LOG.error("Draft 생성 실패: %s", e)
            return "FAILED"
