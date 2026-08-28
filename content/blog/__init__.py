# -*- coding: utf-8 -*-
"""
content/blog/__init__.py — 블로그 콘텐츠 엔진 + Golden 10 Contract

adapter 레이어: content.calculator 의 intent별 프롬프트/템플릿을
블로그 콘텐츠 생성 라인에서 재사용하는 얇은 어댑터.

계산기 파이프라인(modules/calculator_pipeline.py)과 분리된 독립 경로.

Golden 10 Contract:
  - 10개 블로그 콘텐츠의 authoritative source
  - intent별 구조 기준
  - article_content 보호 대상 목록
"""
from dataclasses import dataclass
from typing import List


# ============================================================
# Golden 10 Contract — authoritative source
# ============================================================

VALID_INTENTS = frozenset({"eligibility", "howto", "documents", "calculator"})


@dataclass(frozen=True)
class GoldenContent:
    """Golden 10 블로그 콘텐츠 각 항목의 계약."""
    slug: str          # calculators 테이블의 slug
    intent: str        # 검색 의도
    title: str         # 콘텐츠 제목
    description: str   # 콘텐츠 설명


# Golden 10 — 10건 전체 (authoritative list)
GOLDEN_10: List[GoldenContent] = [
    GoldenContent(
        slug="severance-pay",
        intent="eligibility",
        title="퇴직금 받을 수 있나요? 자격 요건과 계산 방법",
        description="퇴직금 지급 대상, 근로시간 조건, 제외 대상, 계산 방법",
    ),
    GoldenContent(
        slug="weekly-holiday-allowance",
        intent="howto",
        title="주휴수당 계산하는 방법과 지급 조건",
        description="주휴수당 이용 절차, 계산 예시, 주의사항",
    ),
    GoldenContent(
        slug="unemployment-benefit",
        intent="eligibility",
        title="실업급여 받을 수 있나요? 자격 조건",
        description="실업급여 지급 대상, 핵심 조건, 제외 대상",
    ),
    GoldenContent(
        slug="four-insurances",
        intent="calculator",
        title="4대보험 계산하는 방법과 요율",
        description="4대보험 계산 원리, 지급 조건, 계산 예시",
    ),
    GoldenContent(
        slug="annual-leave-allowance",
        intent="howto",
        title="연차수당 계산하는 방법과 지급 기준",
        description="연차수당 이용 절차, 계산 예시, 주의사항",
    ),
    GoldenContent(
        slug="severance-pay-documents",
        intent="documents",
        title="퇴직금 관련 서류 준비와 제출 방법",
        description="퇴직금 필수 서류, 발급 방법, 제출 기한",
    ),
    GoldenContent(
        slug="육아휴직_급여_계산기",
        intent="eligibility",
        title="육아휴직 급여 받을 수 있나요? 자격 조건",
        description="육아휴직 급여 지급 대상, 핵심 조건, 계산 방법",
    ),
    GoldenContent(
        slug="연말정산_환급액_계산기",
        intent="calculator",
        title="연말정산 환급액 계산하는 방법",
        description="연말정산 계산 원리, 입력값 설명, 결과 해석",
    ),
    GoldenContent(
        slug="unemployment-benefit-howto",
        intent="howto",
        title="실업급여 신청하는 방법과 절차",
        description="실업급여 이용 절차, 필요한 정보, 주의사항",
    ),
    GoldenContent(
        slug="four-insurances-documents",
        intent="documents",
        title="4대보험 관련 서류 준비와 확인 방법",
        description="4대보험 필수 서류, 발급 방법, 제출 방법",
    ),
]


# slug → GoldenContent 매핑 (빠른 조회용)
_GOLDEN_MAP = {gc.slug: gc for gc in GOLDEN_10}


def is_golden10(slug: str) -> bool:
    """slug가 Golden 10에 포함되어 있는지 확인."""
    return slug in _GOLDEN_MAP


def get_golden10(slug: str) -> GoldenContent | None:
    """slug에 해당하는 Golden 10 항목을 반환."""
    return _GOLDEN_MAP.get(slug)


def validate_intent(intent: str) -> bool:
    """intent가 유효한지 검증."""
    return intent in VALID_INTENTS


def get_content_request(slug: str, intent: str, title: str,
                         main_keyword: str = None, seo: dict = None,
                         example_context: dict = None, calculator_link: str = None) -> dict:
    """Blog ContentRequest 생성 (Scheduler → Blog adapter 연결 계약).

    Returns:
        ContentRequest dict with all required fields.
    """
    if not validate_intent(intent):
        raise ValueError(f"Invalid intent: {intent}. Must be one of {VALID_INTENTS}")
    return {
        "slug": slug,
        "intent": intent,
        "title": title,
        "main_keyword": main_keyword or title,
        "seo": seo or {},
        "example_context": example_context,
        "calculator_link": calculator_link,
        "content_type": "blog",
    }
