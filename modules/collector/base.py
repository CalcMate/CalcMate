"""
modules/collector/base.py — Collector 추상 기반 클래스
새 source_type 추가 시 이 클래스를 상속하여 collect()만 구현.
"""
from abc import ABC, abstractmethod


class BaseCollector(ABC):
    @abstractmethod
    def collect(self, cfg: dict, site: dict = None) -> list[dict]:
        """
        수집 결과 반환.
        각 item은 최소한 다음 키를 포함해야 함:
          - title, description, link, source_type, site_id
        """
