# -*- coding: utf-8 -*-
"""publish_gate.py — 최종 결과에 따른 발행 결정"""
from .wordpress_publisher import WordPressPublisher
from modules.config_loader import load_config

class PublishGate:
    def __init__(self):
        self.publisher = WordPressPublisher(load_config())

    def gate(self, quality_result, metadata):
        print(f"DEBUG GATE: quality_result={quality_result}, metadata={metadata}")
        status = quality_result.get("status")
        
        if status == "PASS":
            return self.create_draft_with_log(metadata, "대기중(검수필요)")
        elif status == "WARNING":
            self.create_draft_with_log(metadata, "대기중(검수필요, WARNING 포함)")
            return "PUBLISHED_WITH_WARNING_LOG"
        elif status == "REWRITE":
            return "BLOCK_REWRITE"
        elif status == "HOLD":
            return "BLOCK_HOLD_ALERT"
        return "BLOCK_UNKNOWN"

    def create_draft_with_log(self, metadata, message):
        post_id = self.publisher.create_draft(metadata)
        if post_id == "FAILED":
            return "FAILED"
        return "PUBLISHED"
