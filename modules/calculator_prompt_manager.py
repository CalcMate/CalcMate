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


def get_article_prompt(calc: dict, seo: dict = None, faq: list = None) -> tuple:
    seo = seo or {}
    system = ("너는 10년차 SEO 콘텐츠 에디터다. 아래 계산기 주제로 블로그 글을 작성한다.\n"
              "[구조 — 순서 준수] 1)Hero(제목+핵심 한 줄 설명) 2)입력(계산기 입력폼 안내) 3)결과(결과 해설) "
              "4)계산 원리(수식이 아닌 한국어 설명 + 예시 계산 1개 이상) 5)주의사항 "
              "6)자주 묻는 질문 7)관련 계산기 8)CTA\n"
              "[계산식 표기] 계산식을 코드(<code> 태그·변수명·수식 기호) 형태로 노출하지 않는다. "
              "'계산 원리'를 한국어로 설명하고 구체적 숫자 예시를 1개 이상 포함한다.\n"
              "  예) ❌ hourly_wage*(weekly_hours/40*8)   "
              "✅ '시급에 (주당 근로시간 ÷ 40 × 8)을 곱해 계산합니다. 시급 10,000원·주 40시간이면 "
              "10,000 × (40 ÷ 40 × 8) = 80,000원이 됩니다.'\n"
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
