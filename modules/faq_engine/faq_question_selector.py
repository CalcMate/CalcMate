# -*- coding: utf-8 -*-
"""faq_question_selector.py — 검색 의도 및 데이터 기반 질문 선정"""
from .faq_source_mapper import mapper

class FAQQuestionSelector:
    def __init__(self):
        self.mapper = mapper

    def select_questions(self, calculator_slug):
        """계산기 slug를 기준으로 5개 카테고리별 질문 후보를 선정."""
        source_data = self.mapper.get_source_data(calculator_slug, "all")
        if not source_data:
            return {}

        # 카테고리별 질문 선정 로직 (규칙 기반)
        questions = {
            "calculation_logic": [f"{source_data['name']}은 어떻게 계산하나요?"],
            "legal_question": [f"{source_data['name']}의 법적 근거는 무엇인가요?"],
            "exception_case": [f"{source_data['name']} 계산 시 주의해야 할 예외 사항이 있나요?"],
            "misconception": [f"{source_data['name']}에 대해 흔히 하는 오해는 무엇인가요?"],
            "usage_method": [f"{source_data['name']}을 어떻게 사용하나요?"]
        }
        return questions
