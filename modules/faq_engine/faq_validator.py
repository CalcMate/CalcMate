# -*- coding: utf-8 -*-
"""faq_validator.py — 법령/계산 규칙 검증 게이트"""
from .faq_source_mapper import mapper

class FAQValidator:
    def __init__(self):
        self.mapper = mapper

    def validate(self, faq_content, category, calculator_slug):
        """답변 내용이 source_mapper의 데이터와 일치하는지 검증."""
        source_data = self.mapper.get_source_data(calculator_slug, category)
        if not source_data:
            return False, "HOLD: Mapping 데이터 없음"

        # 1. 법령 근거 검증
        if category == "legal_question" and source_data.get('law') and source_data.get('law') not in faq_content:
            return False, f"HOLD: 법령 근거 누락 ({source_data.get('law')})"

        # 2. 계산 규칙 검증 (공통 규칙 적용)
        rules = source_data.get("compute_rules", {})
        
        # Threshold 규칙
        if "min_weekly_hours" in rules:
            is_valid, msg = self.validate_threshold_rule(faq_content, rules, "min_weekly_hours", "시간")
            if not is_valid: return is_valid, msg
        
        # Transition 규칙 (육아휴직)
        if "transition_points" in rules:
            is_valid, msg = self.validate_transition_rule(faq_content, rules)
            if not is_valid: return is_valid, msg

        return True, "검증 통과"

    def validate_threshold_rule(self, content, rules, rule_key, unit):
        threshold = rules.get(rule_key)
        if threshold and any(f"{i}{unit}" in content for i in range(1, threshold)):
            return False, f"HOLD: 계산 규칙 위반 ({threshold}{unit} 이상 필요)"
        return True, "통과"

    def validate_numeric_rule(self, content, rules, rule_key, calculator_slug):
        """본문/FAQ 내 숫자와 계산기 규칙 간 일치 여부 검증."""
        expected_value = rules.get(rule_key)
        if expected_value and str(expected_value) not in content:
            return False, f"HOLD: 숫자 불일치 ({rule_key} 기대값: {expected_value})"
        return True, "통과"

    def validate_condition_rule(self, content, rules, rule_key):
        return True, "통과"

    def validate_exception_rule(self, content, rules, rule_key):
        return True, "통과"

    def validate_transition_rule(self, content, rules):
        """전환 시점(transition point)과 그에 따른 로직 변화를 검증."""
        # 1. 전환 시점 언급 여부 확인
        points = rules.get("transition_points", [])
        for p in points:
            if str(p) not in content:
                return False, f"HOLD: 전환 시점 {p} 관련 정보 누락"

        # 2. 전환 구간에서의 잘못된 서술(동일성 주장 등) 감지
        keywords = rules.get("comparison_keywords", ["동일", "같음"])
        if any(k in content for k in keywords):
            return False, f"HOLD: 전환 시점 구간별 조건 차이 확인 필요 ({', '.join(keywords)} 서술)"

        return True, "통과"
