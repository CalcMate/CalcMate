# -*- coding: utf-8 -*-
"""intent_analyzer.py — 검색의도 충족도 검사"""

class IntentAnalyzer:
    def __init__(self):
        # 예시: 계산기별 필수 요소 매핑
        self.requirements = {
            "weekly-holiday-allowance": ["계산방법", "지급조건", "계산예시"]
        }

    def analyze(self, content, calculator_slug):
        required = self.requirements.get(calculator_slug, [])
        missing = [req for req in required if req not in content]
        score = 100 - (len(missing) * 20)
        return max(0, score), missing
