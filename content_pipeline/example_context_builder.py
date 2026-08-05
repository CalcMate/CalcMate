# -*- coding: utf-8 -*-
"""example_context_builder.py — 계산기 결과를 콘텐츠 생성용 데이터로 변환"""

class ExampleContextBuilder:
    def build(self, calculator_id: str, inputs: dict, result: dict) -> dict:
        """계산기 결과를 콘텐츠 생성용 JSON 구조로 빌드합니다."""
        return {
            "calculator": calculator_id,
            "example_type": "standard_case",
            "inputs": inputs,
            "calculation_result": result,
            "source": "calculator_core"
        }
