# -*- coding: utf-8 -*-
"""structure_checker.py — 문단 구조 검사"""

class StructureChecker:
    def check(self, content):
        standard_sections = ["서론", "계산 방법", "주의사항", "FAQ"]
        # 간단한 순서 체크
        indices = [content.find(s) for s in standard_sections]
        if -1 in indices:
            missing = [standard_sections[i] for i, idx in enumerate(indices) if idx == -1]
            return False, missing
        
        is_ordered = all(indices[i] < indices[i+1] for i in range(len(indices)-1))
        return is_ordered, []
