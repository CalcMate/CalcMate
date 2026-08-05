# -*- coding: utf-8 -*-
"""topic_extractor.py — 경쟁 문서 주제 추출"""

class TopicExtractor:
    def __init__(self):
        # 기본적인 정규화 맵
        self.normalization_map = {
            "계산 공식": "계산 방법",
            "계산법": "계산 방법",
            "지급요건": "지급 조건"
        }

    def _normalize(self, topic: str) -> str:
        return self.normalization_map.get(topic, topic)

    def extract(self, competitor_profiles: list[dict]) -> dict:
        frequency = {}
        for profile in competitor_profiles:
            for section in profile.get("sections", []):
                norm_topic = self._normalize(section)
                frequency[norm_topic] = frequency.get(norm_topic, 0) + 1
        
        # 최소 2번 이상 등장한 것을 공통 주제로 간주
        common_topics = [t for t, count in frequency.items() if count >= 2]
        
        return {
            "common_topics": common_topics,
            "topic_frequency": frequency
        }
