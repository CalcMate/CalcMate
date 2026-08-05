# -*- coding: utf-8 -*-
"""faq_generator.py — 매핑된 데이터를 바탕으로 근거 기반 답변 생성"""
from .faq_source_mapper import mapper

class FAQGenerator:
    def __init__(self):
        self.mapper = mapper

    def generate(self, question, category, calculator_slug):
        """질문과 카테고리를 받아 매핑된 데이터를 사용하여 근거 기반 답변 생성."""
        source_data = self.mapper.get_source_data(calculator_slug, category)
        if not source_data:
            return "정보 없음"

        # LLM 프롬프트 구성 (근거 데이터 준수)
        # ⚠️ 구현 상세는 추후 LLM 호출 로직으로 구체화
        
        # 예시 답변 생성 (실제 구현 시 LLM 호출)
        if category == "legal_question":
            return f"{source_data['name']}의 법적 근거는 {source_data['law']} {source_data['article']}입니다."
        
        return f"{source_data['name']}에 대한 {category} 답변입니다."
