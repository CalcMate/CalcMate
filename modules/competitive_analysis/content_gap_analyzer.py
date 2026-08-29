# -*- coding: utf-8 -*-
"""content_gap_analyzer.py — 경쟁 문서와의 콘텐츠 갭 분석"""

class ContentGapAnalyzer:
    def __init__(self):
        # 필수 Topic 정의 (누락 시 즉시 HIGH 우선순위)
        self.essential_topics = ["지급 조건", "법적 기준", "FAQ"]

    def analyze(self, our_profile: dict, competitor_topics: dict) -> dict:
        """경쟁사 대비 부족한 콘텐츠 토픽을 탐지합니다."""
        
        our_topics = set(our_profile.get("topics", []))
        competitor_common = set(competitor_topics.get("common_topics", []))
        
        missing_topics = sorted(competitor_common - our_topics)
        
        if not missing_topics:
            return {"missing_topics": [], "priority": "LOW"}
        
        # 우선순위 결정: 필수 항목 누락 시 HIGH
        if any(topic in self.essential_topics for topic in missing_topics):
            priority = "HIGH"
        else:
            priority = "MEDIUM"
                
        return {
            "missing_topics": missing_topics,
            "priority": priority
        }
