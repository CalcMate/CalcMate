# -*- coding: utf-8 -*-
"""faq_position_checker.py — FAQ 배치 검사"""

class FAQPositionChecker:
    def check(self, content):
        faq_idx = content.find("FAQ")
        if faq_idx == -1:
            return "WARNING", "FAQ 없음"
        
        # 전체 길이의 50% 이후에 위치해야 함
        if faq_idx < len(content) * 0.5:
            return "HOLD", "FAQ가 너무 앞에 위치함"
            
        return "PASS", "통과"
