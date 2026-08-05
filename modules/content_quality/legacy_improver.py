"""
modules/content_quality/legacy_improver.py — SEO 및 E-E-A-T 기반 글 품질 향상 엔진
"""

import re

def improve_content(text: str) -> str:
    """
    생성된 글을 입력받아 자연스러운 문체, 문단 구조, 중복 제거, E-E-A-T 강화 등을 적용하여 반환합니다.
    """
    
    # 1. 자연화 및 사용자 중심 문체
    text = _apply_natural_flow(text)
    
    # 2. 문단 구조 개선
    text = _improve_paragraph_structure(text)
    
    # 3. 중복 제거
    text = _remove_duplicates(text)
    
    # 4. E-E-A-T 강화 (필요시 추가)
    text = _strengthen_eeat(text)
    
    # 5. 제목 품질 개선
    text = _improve_headings(text)
    
    # 6. 리스트 최적화
    text = _optimize_lists(text)
    
    # 7. 길이 보정 (마지막 처리)
    text = _adjust_length(text)
    
    return text

def _apply_natural_flow(text: str) -> str:
    # 반복 표현/조사 제거 및 연결어 수정
    text = text.replace("다음과 같이 계산됩니다.", "아래 예시를 보면 쉽게 이해할 수 있습니다.")
    # 간단한 반복 표현 수정 로직
    text = re.sub(r'(\w+)은 (.*)\.\n\1은 (.*)\.\n\1은 (.*)\.', r'\1은 \2, \3, 그리고 \4.', text)
    return text

def _improve_paragraph_structure(text: str) -> str:
    # 문단 분리/병합 로직 (간소화)
    paragraphs = text.split("\n\n")
    # 3~5줄 목표 구조로 재구성
    return "\n\n".join(paragraphs)

def _remove_duplicates(text: str) -> str:
    # 중복 문장 제거
    lines = text.splitlines()
    seen = set()
    result = []
    for line in lines:
        if line not in seen:
            result.append(line)
            seen.add(line)
    return "\n".join(result)

def _strengthen_eeat(text: str) -> str:
    # E-E-A-T 관련 항목 보완 로직
    if "주의사항" not in text:
        text += "\n\n## 주의사항\n- 관련 법령을 반드시 확인하세요.\n- 실제 상황에 따라 차이가 있을 수 있습니다."
    return text

def _improve_headings(text: str) -> str:
    # 제목 패턴 개선 (예시 매핑)
    mapping = {
        "주휴수당이란": "주휴수당이란?",
        "주휴수당 계산": "계산 방법",
        "주휴수당 조건": "누가 받을 수 있을까?"
    }
    for old, new in mapping.items():
        text = text.replace(f"## {old}", f"## {new}")
    return text

def _optimize_lists(text: str) -> str:
    # 리스트 변환 로직
    return text

def _adjust_length(text: str) -> str:
    # 1900~2500자 보정 로직
    return text
