# -*- coding: utf-8 -*-
"""competitor_parser.py — 경쟁 문서 구조 분석"""
import re

class CompetitorParser:
    def parse(self, content: str) -> dict:
        """경쟁 문서의 구조 정보를 추출합니다."""
        
        # 1. 제목 추출 (# 또는 <title>)
        title_match = re.search(r'# (.+)|<title>(.+)</title>', content)
        title = ""
        if title_match:
            title = title_match.group(1) or title_match.group(2)
        
        # 2. Section 추출 (## / ### 또는 <h2> / <h3>)
        sections = re.findall(r'#{2,3}\s+(.+)|<h[23]>(.+)</h[23]>', content)
        flattened_sections = [s[0] or s[1] for s in sections]
        
        # 3. FAQ 탐지 (?, FAQ, 자주 묻는 질문, Q.)
        faq_patterns = [r'\?', r'FAQ', r'자주 묻는 질문', r'Q\.']
        faq_count = sum(len(re.findall(p, content, re.IGNORECASE)) for p in faq_patterns)
        
        # 4. Table 탐지 (| 또는 <table>)
        table_count = len(re.findall(r'\||<table>', content))
        
        # 5. Example 탐지 (숫자+원/달러 또는 '예시')
        example_count = len(re.findall(r'\d+원|\d+달러|예시', content))
        
        # 6. Source 탐지 (출처, 참고)
        source_count = len(re.findall(r'출처|참고', content))
        
        return {
            "title": title.strip(),
            "sections": [s.strip() for s in flattened_sections],
            "faq_count": faq_count,
            "table_count": table_count,
            "example_count": example_count,
            "source_count": source_count
        }
