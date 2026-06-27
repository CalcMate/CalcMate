# -*- coding: utf-8 -*-
"""
modules/calculator_prompt_manager.py — 계산기 프롬프트 중앙 관리 (SalaryMate 자동생성, 신규)

SEO/FAQ/본문/CTA/이미지 프롬프트를 한 곳에서 관리. 각 함수는 (system, user) 튜플 반환.
품질 규칙(AI 티 표현 금지, 키워드 스팸 금지)을 모든 시스템 프롬프트에 주입.
"""
import json

# 공통 품질 규칙 (모든 프롬프트에 포함)
QUALITY = (
    "[작성 규칙]\n"
    "- 'AI가 작성했습니다', 'ChatGPT', 'Claude', 'Gemini' 같은 표현 절대 금지.\n"
    "- 키워드 스팸/과도한 SEO 반복 금지. 자연스러운 한국어.\n"
    "- 실제 사용자의 검색의도를 충족하는 실용 정보 중심. 광고성 과장 금지."
)


def _ctx(calc: dict) -> str:
    return (f"계산기명: {calc.get('name','')}\n"
            f"카테고리: {calc.get('category','')}\n"
            f"설명: {calc.get('seo_desc','') or calc.get('seo_description','')}\n"
            f"계산공식: {calc.get('formula','')}\n"
            f"입력항목: {calc.get('input_schema','')}\n"
            f"출력항목: {calc.get('output_schema','')}")


def get_seo_prompt(calc: dict) -> tuple:
    system = ("너는 SEO 전문가다. 계산기에 대한 검색 최적화 제목과 메타설명을 작성한다.\n"
              "제목 28~40자(연도 포함 가능), 메타설명 70~120자.\n" + QUALITY + "\n"
              '순수 JSON만 반환: {"seo_title":"","seo_description":""}')
    return system, _ctx(calc)


def get_faq_prompt(calc: dict, n_min: int = 5, n_max: int = 10) -> tuple:
    system = (f"너는 해당 분야 전문가다. 사용자가 실제로 궁금해하는 FAQ를 {n_min}~{n_max}개 작성한다.\n"
              "각 답변은 2~4문장, 구체적이고 정확하게.\n" + QUALITY + "\n"
              '순수 JSON만 반환: {"faq":[{"question":"","answer":""}]}')
    return system, _ctx(calc)


def get_article_prompt(calc: dict, seo: dict = None, faq: list = None) -> tuple:
    seo = seo or {}
    system = ("너는 10년차 SEO 콘텐츠 에디터다. 아래 계산기 주제로 블로그 글을 작성한다.\n"
              "[구조] 서론 → 계산기 설명 → 계산 방법(공식+숫자 예시) → 실제 예시 → 주의사항 → 자주 묻는 질문 → CTA\n"
              "분량 공백 포함 2000자 이상. 애드센스 친화적(정보 충실). HTML로 출력하고 "
              "[BODY_HTML_START]...[BODY_HTML_END] 태그로 감싼다.\n"
              "CTA에는 '아래 SalaryMate 계산기를 이용하면 자동으로 계산할 수 있습니다.' 취지 문장 포함.\n" + QUALITY)
    user = (_ctx(calc) +
            f"\nSEO제목: {seo.get('seo_title','')}\n메타설명: {seo.get('seo_description','')}\n"
            f"FAQ: {json.dumps(faq or [], ensure_ascii=False)}")
    return system, user


def get_cta_prompt(calc: dict) -> tuple:
    system = ("계산기 사용을 유도하는 자연스러운 CTA 문장 1~2개를 작성한다. 과장/광고 금지.\n" + QUALITY +
              "\n순수 텍스트만 반환.")
    return system, _ctx(calc)


def get_image_prompt(calc: dict) -> tuple:
    system = ("너는 이미지 프롬프트 디자이너다. 블로그 썸네일/본문용 영문 이미지 프롬프트를 작성한다.\n"
              "사실적·전문적. 텍스트 삽입 지시 금지.\n"
              '순수 JSON만 반환: {"thumbnail":"","body":""}')
    return system, _ctx(calc)
