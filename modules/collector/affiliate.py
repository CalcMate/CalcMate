"""
modules/collector/affiliate.py — 어필리에이트 상품 DB 수집기 (stub)
향후 상품 DB 연동 시 이 파일에 구현.
"""
from .base import BaseCollector


class AffiliateCollector(BaseCollector):
    def collect(self, cfg: dict, site: dict = None) -> list[dict]:
        # stub — 상품 DB 연동 후 구현
        print("[AffiliateCollector] stub: 미구현")
        return []
