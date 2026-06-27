"""
modules/collector/finance.py — 금융 키워드 수집기 (stub)
향후 금융 API / 키워드 DB 연동 시 구현.
"""
from .base import BaseCollector


class FinanceCollector(BaseCollector):
    def collect(self, cfg: dict, site: dict = None) -> list[dict]:
        print("[FinanceCollector] stub: 미구현")
        return []
