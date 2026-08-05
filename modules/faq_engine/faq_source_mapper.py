# -*- coding: utf-8 -*-
"""faq_source_mapper.py — FAQ 시스템의 중앙 데이터 매핑 허브

질문(의도) → 계산기 → 법령(legal_basis) → 불변식(Invariant) 매핑을 담당합니다.
나머지 모듈(generator, selector, validator)은 반드시 이 모듈을 통해 데이터를 조회해야 합니다.
"""

import yaml
from pathlib import Path

# ── 상수 및 경로 ──────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LEGAL_BASIS_PATH = BASE_DIR / "docs" / "legal_basis.master.yaml"

# ── 매핑 테이블 (설계안) ──────────────────────────────────────────────────────
# 실제 운영 시에는 별도 YAML로 관리할 수도 있음. 여기서는 구조 정의.

class FAQSourceMapper:
    def __init__(self):
        self._legal_data = self._load_legal_basis()
        self._mapping_table = self._initialize_mapping()

    def _load_legal_basis(self):
        with open(LEGAL_BASIS_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _initialize_mapping(self):
        # 질문 타입별 매핑 정의
        return {
            "calculation_logic": [], # 계산 로직 관련
            "legal_question": [],    # 법령 근거 질문
            "exception_case": [],    # 예외 케이스(Invariant/Exception)
            "misconception": [],     # 오해 바로잡기
            "usage_method": []       # 사용 방법 UI
        }

    def get_source_data(self, calculator_slug, category):
        """계산기 slug와 카테고리를 받아 관련 법령/불변식 데이터를 반환."""
        if calculator_slug not in self._legal_data:
            return None
        
        # legal_basis.master.yaml 데이터를 기반으로 매핑
        return self._legal_data.get(calculator_slug)

# ── 싱글톤 인스턴스 (혹은 의존성 주입) ──────────────────────────────────────────

mapper = FAQSourceMapper()
