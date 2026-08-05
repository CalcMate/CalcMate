# -*- coding: utf-8 -*-
"""quality_validator.py — 종합 품질 판정"""
from .intent_analyzer import IntentAnalyzer
from .information_density import InformationDensity
from .eeat_checker import EEATChecker
from .structure_checker import StructureChecker
from .example_checker import ExampleChecker
from .faq_position_checker import FAQPositionChecker

class QualityValidator:
    def __init__(self):
        self.intent = IntentAnalyzer()
        self.density = InformationDensity()
        self.eeat = EEATChecker()
        self.structure = StructureChecker()
        self.example = ExampleChecker()
        self.faq_pos = FAQPositionChecker()

    def validate(self, content, calculator_slug, compute_rules=None):
        # 1. 예외 규칙 (즉시 HOLD)
        if compute_rules:
            is_valid, msg = self.example.check(content, compute_rules, "min_wage", calculator_slug)
            if not is_valid: return "HOLD"

        # 2. 종합 점수 계산
        intent_score, _ = self.intent.analyze(content, calculator_slug)
        density_score, _ = self.density.evaluate(content)
        
        avg_score = (intent_score + density_score) / 2
        
        if avg_score >= 90: return "PASS"
        if avg_score >= 70: return "WARNING"
        if avg_score >= 50: return "REWRITE"
        return "HOLD"
