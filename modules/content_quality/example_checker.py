# -*- coding: utf-8 -*-
"""example_checker.py — 예시/사례 숫자 검증"""
from modules.faq_engine.faq_validator import FAQValidator

class ExampleChecker:
    def __init__(self):
        self.validator = FAQValidator()

    def check(self, content, rules, rule_key, calculator_slug):
        # H-3 validator 규칙 재사용
        return self.validator.validate_numeric_rule(content, rules, rule_key, calculator_slug)
