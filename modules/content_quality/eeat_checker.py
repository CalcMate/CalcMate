# -*- coding: utf-8 -*-
"""eeat_checker.py — E-E-A-T 요소 검사"""

class EEATChecker:
    def check(self, content):
        checks = {
            "experience": "예시" in content,
            "expertise": "법령" in content,
            "authority": "출처" in content,
            "trust": "주의사항" in content
        }
        return all(checks.values()), checks
