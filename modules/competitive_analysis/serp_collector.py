# -*- coding: utf-8 -*-
"""serp_collector.py — 검색 데이터 수집 인터페이스"""
from abc import ABC, abstractmethod

class SERPProvider(ABC):
    @abstractmethod
    def get_serp(self, keyword: str) -> list[dict]:
        pass

class MockSERPProvider(SERPProvider):
    def get_serp(self, keyword: str) -> list[dict]:
        # Mock 5 results
        return [
            {"title": f"Mock Result {i} for {keyword}", "url": f"https://mock{i}.com", "description": "Mock description"}
            for i in range(1, 6)
        ]

class SERPCollector:
    def __init__(self, provider: SERPProvider):
        self.provider = provider
    
    def collect(self, keyword: str) -> dict:
        if not keyword or not isinstance(keyword, str):
            raise ValueError("Invalid keyword")
        
        results = self.provider.get_serp(keyword)
        return {"keyword": keyword, "results": results}
