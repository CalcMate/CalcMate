# -*- coding: utf-8 -*-
"""improvement_generator.py — 콘텐츠 개선 작업 목록 생성"""

class ImprovementGenerator:
    def __init__(self):
        # Action/Reason 매핑
        self.action_map = {
            "FAQ": {"action": "FAQ 섹션 추가", "reason": "주요 사용자 질문 보완"},
            "법적 기준": {"action": "법적 기준 설명 추가", "reason": "최신 법령 명시"},
            "지급 조건": {"action": "대상 조건 설명 추가", "reason": "수급 조건 구체화"},
            "예시": {"action": "계산 예시 추가", "reason": "실제 데이터 기반 사례 제공"},
            "표": {"action": "비교 표 추가", "reason": "데이터 가독성 개선"}
        }
        self.default_action = {"action": "설명 확장", "reason": "문장 다듬기"}

    def generate(self, gap_result: dict) -> dict:
        """Gap 결과를 기반으로 콘텐츠 개선 작업을 생성합니다."""
        tasks = []
        priority = gap_result.get("priority", "LOW")
        
        for topic in gap_result.get("missing_topics", []):
            action_info = self.action_map.get(topic, self.default_action)
            tasks.append({
                "topic": topic,
                "priority": priority,
                "action": action_info["action"],
                "reason": action_info["reason"]
            })
        return {"tasks": tasks}
