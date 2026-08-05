"""
modules/search_intent.py — 검색 의도 자동 분석 엔진
"""

INTENT_STRUCTURES = {
    "INFORMATIONAL": [
        "정의", "대상", "조건", "계산기", "FAQ", "주의사항"
    ],
    "COMMERCIAL": [
        "장점", "비교", "계산기", "FAQ"
    ],
    "TRANSACTIONAL": [
        "계산기", "예시 계산", "절약팁", "FAQ"
    ],
    "MIXED": [
        "정의", "계산기", "예시", "FAQ", "관련 계산기"
    ]
}

def analyze_intent(calculator_name: str, main_keyword: str, longtail_keyword: str) -> dict:
    """
    입력된 키워드와 계산기 이름을 바탕으로 검색 의도를 판단하고 글 구조를 반환합니다.
    """
    
    # 판단 로직 (Simple Rule-based approach based on provided examples)
    text = (calculator_name + " " + main_keyword + " " + longtail_keyword).lower()
    
    if any(word in text for word in ["계산기", "계산"]):
        if any(word in text for word in ["이란", "정의", "방법"]):
            intent = "INFORMATIONAL"
        elif any(word in text for word in ["비교", "장점", "추천"]):
            intent = "COMMERCIAL"
        else:
            # 기본값
            intent = "TRANSACTIONAL"
            
        # "퇴직금 계산"과 같은 경우 MIXED로 분류
        if "퇴직금" in text and "계산" in text:
            intent = "MIXED"
    else:
        intent = "INFORMATIONAL"

    return {
        "intent": intent,
        "structure": INTENT_STRUCTURES.get(intent, [])
    }
