"""
cleaner.py — STEP 2: 행정 용어 청소 / STEP 9: 정규식 파싱
프롬프트: PART 3-B
"""
import json, re
from .ai_provider import build_provider, retry_call
from .utils.parser import parse_json_lenient

SYSTEM_CLEANER = """너는 정부 정책 원문 데이터를 AI 파이프라인이 처리할 수 있는 순수한 정보 단위로 정제하는 데이터 클리너다.
아래에 입력된 RSS 원문 데이터를 분석하고, 불필요한 행정 수식어를 제거한 뒤 지정된 JSON 구조로만 출력하라.

[정제 규칙]
1. 행정 수식어 제거: "이번에","적극적으로","관련하여","지원하고자","추진 중인","해당되는 분들께서는" 등 제거
2. 핵심 정보 추출: 정책명, 지원 대상, 지원 내용, 신청 기간, 마감일 식별. 없으면 null.
3. 중립적 서술어: 모든 문장을 "~임","~함","~가능" 형태 명사형 단문으로 축약
4. clean_summary: 100자 이상 200자 이하
5. 카테고리: [복지,고용,창업,교육,주거,금융,의료,환경,농업,기타] 중 1개

인사말 없이 순수 JSON만 반환하라:
{"clean_policy_name":"","clean_summary":"","clean_category":"","clean_target":null,"clean_period":null,"clean_deadline":null,"clean_benefit":null,"source_url":""}"""

def clean_rss_item(item: dict, cfg: dict) -> dict:
    provider = build_provider(cfg["ORCHESTRATOR_PROVIDER"], cfg)  # MODEL_CLEANER용
    model = cfg["MODEL_CLEANER"]
    user_msg = f"원문제목: {item['title']}\n원문요약: {item['description']}\n출처URL: {item['link']}\n카테고리추정: {item['category']}"

    def _call():
        text, tokens = provider.chat(SYSTEM_CLEANER, user_msg, model, max_tokens=800)
        return text, tokens

    raw, tokens = retry_call(_call, cfg.get("MAX_RETRY_COUNT", 3))
    try:
        data = parse_json_lenient(raw)
    except Exception:
        # JSON 파싱 실패 시 원본 반환
        data = {"clean_policy_name": item["title"], "clean_summary": item["description"][:200],
                "clean_category": "기타", "clean_target": None, "clean_period": None,
                "clean_deadline": None, "clean_benefit": None, "source_url": item["link"]}
    data["_tokens"] = tokens
    return data

def parse_html_body(text: str) -> str:
    """STEP 9: [BODY_HTML_START]~[BODY_HTML_END] 태그 추출"""
    m = re.search(r"\[BODY_HTML_START\](.*?)\[BODY_HTML_END\]", text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()
