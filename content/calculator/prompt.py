# -*- coding: utf-8 -*-
"""
modules/calculator_prompt_manager.py — 계산기 프롬프트 중앙 관리 (SalaryMate 자동생성, 신규)

SEO/FAQ/본문/CTA/이미지 프롬프트를 한 곳에서 관리. 각 함수는 (system, user) 튜플 반환.
품질 규칙(AI 티 표현 금지, 키워드 스팸 금지)을 모든 시스템 프롬프트에 주입.
"""
import json
from datetime import datetime

# 연도 동적 주입(하드코딩 금지). 모듈 로드 시점의 현재 연도.
CURRENT_YEAR = datetime.now().year

# 공통 품질 규칙 (모든 프롬프트에 포함)
QUALITY = (
    "[작성 규칙]\n"
    "- 'AI가 작성했습니다', 'ChatGPT', 'Claude', 'Gemini' 등 AI 관련 표현 절대 금지.\n"
    "- 키워드 스팸/과도한 SEO 반복 금지. 자연스러운 한국어.\n"
    "- 실제 사용자의 검색의도를 충족하는 실용 정보 중심. 광고성 과장 금지.\n"
    f"- 연도는 하드코딩 금지. 연도가 필요하면 현재 연도({CURRENT_YEAR})만 사용한다. '2023년'·'2022년' 등 고정 연도 금지.\n"
    "- 법령·요율(최저임금·보험료율·퇴직금 기준 등)은 입력/시스템 제공 값만 사용하고, 확인되지 않은 수치·변경사항은 추측하지 않는다.\n"
    "- 업데이트 내역·콘텐츠 생성일·검수일 등 내부 운영 정보 표기 절대 금지."
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
              f"제목 28~40자(연도가 필요하면 {CURRENT_YEAR}만 사용, 고정 연도 금지), 메타설명 70~120자.\n"
              + QUALITY + "\n"
              '순수 JSON만 반환: {"seo_title":"","seo_description":""}')
    return system, _ctx(calc)


def get_faq_prompt(calc: dict, n_min: int = 6, n_max: int = 8) -> tuple:
    system = (f"너는 해당 분야 전문가다. 사용자가 실제로 궁금해하는 FAQ를 {n_min}~{n_max}개 작성한다.\n"
              "반드시 다음 6가지를 모두 포함한다: "
              "①지급 조건(누가·언제 받는가) ②예외 사항(받지 못하는 경우) ③계산 기준(정확한 계산 방법) "
              "④자주 틀리는 부분(흔한 오해·실수) ⑤법적 근거(관련 법령 조항) ⑥실무 팁(사용 시 주의사항).\n"
              "각 답변은 구체적인 수치·조건·예외를 포함하고 2~4문장으로 작성한다. "
              "'~할 수 있습니다', '~중요합니다' 같은 공허한 답변 금지.\n" + QUALITY + "\n"
              '순수 JSON만 반환: {"faq":[{"question":"","answer":""}]}')
    return system, _ctx(calc)


def get_article_prompt(calc: dict, seo: dict = None, faq: list = None, example_context: dict = None, intent: str = None) -> tuple:
    seo = seo or {}
    example_str = json.dumps(example_context, ensure_ascii=False) if example_context else "제공된 계산 데이터 없음"

    # 템플릿 분기
    # 템플릿 분기
    if intent == "eligibility":
        structure = (
            "1. 서론(대상자 중심 문제제기)\n"
            "2. 지급 대상(주휴수당을 지급받을 수 있는 대상자 요건)\n"
            "3. 근로시간 조건(주 15시간 이상 등 충족해야 할 기준)\n"
            "4. 제외 대상(지급받지 못하는 예외 상황)\n"
            "5. 계산 방법(공식+계산 근거)\n"
            "6. FAQ\n"
        )
        system_instructions = (
            "작성 규칙: 'eligibility' 의도로 작성하라. "
            "반드시 본문 최상단에 서론을 배치하고, 바로 뒤에 '지급 대상', '근로시간 조건', '제외 대상'을 순서대로 명확한 H2로 구성하라. "
            "이후에 계산 방법과 FAQ를 하단에 배치하되, FAQ 섹션의 H2는 반드시 'FAQ' 그대로 사용하라('자주 묻는 질문' 등 다른 표현 금지). "
            "계산기 자체를 소개하거나 '계산기 사용하기' 섹션을 서론 상단에 배치하는 행위를 엄격히 금지한다."
        )
    elif intent == "documents":
        structure = (
            "1. 서론(제출 서류의 중요성)\n"
            "2. 필수 서류 목록\n"
            "3. 서류 발급 방법\n"
            "4. 제출 기한 및 절차\n"
            "5. 주의사항(서류 미비 시)\n"
            "6. FAQ\n"
        )
        system_instructions = "작성 규칙: 'documents' 의도에 맞춰, 제출 서류와 발급/제출 절차를 상세히 서술하라."
    elif intent == "howto":
        structure = (
            "1. 서론(이용 방법 요약)\n"
            "2. 이용 절차 단계별 설명\n"
            "3. 계산기 사용법(CTA 포함)\n"
            "4. 계산 예시\n"
            "5. 자주 묻는 질문\n"
        )
        system_instructions = "작성 규칙: 'howto' 의도에 맞춰, 계산기 사용 절차와 예시를 상세히 서술하라."
    else: # 기본값(calculator)
        structure = (
            "1. 서론(문제제기+검색의도 충족)\n"
            "2. 요약(계산기 목적+핵심 정보)\n"
            "3. 계산기 연결(계산기 CTA+자연스러운 문구)\n"
            "4. 계산 방법(공식 설명+계산 기준+법적 근거)\n"
            "5. 지급조건(대상 조건+제외 조건+중요 기준)\n"
            "6. 계산예시(아래 제공된 계산 데이터만 사용)\n"
            "7. 주의사항(자주 발생하는 오류+잘못 이해하는 부분)\n"
            "8. FAQ(H-3 FAQ 참조)\n"
            "9. 출처(법령 근거+공식 기관 정보)\n"
        )
        system_instructions = "작성 규칙: 계산기 중심의 구조를 유지하며, 계산 방법과 주의사항을 상세히 다룬다."

    system = ("너는 10년차 SEO 콘텐츠 에디터다. 아래 계산기 주제로 블로그 글을 작성한다.\n"
              f"[구조 — 다음 섹션 순서 및 명칭을 엄격히 준수한다]\n{structure}\n"
              f"{system_instructions}\n\n"
              "[필수 용어 사용 규칙 — Validator 통과를 위해 필수]\n"
              "- '계산방법', '지급조건', '계산예시' (Intent용)\n"
              "- '계산 방법', '지급 조건', '예시' (Structure용)\n"
              "[검증된 계산 데이터]\n"
              f"{example_str}\n\n"
              "[숫자 보호 규칙]\n"
              "- 숫자를 임의로 생성하거나 변경하지 않는다.\n"
              "분량 공백 포함 1900자 이상. HTML로 출력하고 "
              "[BODY_HTML_START]...[BODY_HTML_END] 태그로 감싼다.\n" + QUALITY)
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
