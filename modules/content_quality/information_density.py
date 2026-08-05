# -*- coding: utf-8 -*-
"""information_density.py — 정보 밀도 평가"""

class InformationDensity:
    def evaluate(self, content):
        required_elements = ["계산 기준", "주의사항", "예시"]
        found = [el for el in required_elements if el in content]
        score = (len(found) / len(required_elements)) * 100
        missing = [el for el in required_elements if el not in content]
        return score, missing
