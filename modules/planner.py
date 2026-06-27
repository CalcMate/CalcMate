"""
planner.py — M1 Research AI (Gemini Flash)
STEP 6: SEO 기획 + 검색의도 분석 + 콘텐츠 구조 설계

AI 역할 정의서:
  담당: Gemini Flash (research_ai)
  출력: keyword / intent / faq / related_keywords / outline / entities + SEO 메타
"""
import json
from .ai_provider import build_provider_for_role, retry_call
from .utils.parser import parse_json_lenient

# ── M1 Research AI 시스템 프롬프트 ───────────────────────────────────────────
SYSTEM_M1 = """너는 SEO 리서치 전문가다.

주어진 키워드에 대해 검색의도 / 관련 키워드 / FAQ /
콘텐츠 구조 / 관련 엔티티를 조사한다.

결과는 반드시 JSON으로만 출력한다.
불필요한 설명과 마크다운 코드블록은 금지한다.

[역할 경계]
SEO 메타데이터 설계만 수행. 본문 작성 금지.

[SEO 제목 규칙]
- 공백 포함 28자 이상 38자 이하
- 메인 키워드를 제목 앞 1/3 이내 배치
- avoid_patterns 단어 조합 절대 사용 금지
- recent_titles와 유사도 85% 이상 제목 폐기 후 재생성

인사말·코드블록 없이 순수 JSON만 반환:
{
  "keyword": "",
  "intent": "",
  "faq": [],
  "related_keywords": [],
  "outline": [],
  "entities": [],
  "seo_title": "",
  "meta_description": "",
  "tags_list": [],
  "main_keyword": "",
  "longtail_keywords": [],
  "alt_thumbnail": "",
  "alt_body_image": "",
  "image_prompt_thumbnail": "",
  "image_prompt_body": ""
}"""


def plan_seo(clean_data: dict, strategy: dict,
             recent_titles: list[str], cfg: dict,
             site_cfg: dict = None) -> dict:
    """
    M1 Research AI 호출.
    site_cfg 있으면 해당 사이트의 research_ai 프로필 사용.
    """
    provider, model = build_provider_for_role("research", cfg, site_cfg)

    user_msg = (
        f"정책명: {clean_data.get('clean_policy_name')}\n"
        f"핵심요약: {clean_data.get('clean_summary')}\n"
        f"수혜대상: {clean_data.get('clean_target')}\n"
        f"카테고리: {clean_data.get('clean_category')}\n"
        f"소스 타입: {clean_data.get('source_type', 'policy')}\n"
        f"콘텐츠 각도: {strategy.get('content_angle')}\n"
        f"피해야 할 패턴: {strategy.get('avoid_patterns')}\n"
        f"편집 톤: {strategy.get('editorial_tone')}\n"
        f"최근 발행 제목: {json.dumps(recent_titles, ensure_ascii=False)}"
    )

    def _call():
        text, tokens = provider.chat(SYSTEM_M1, user_msg, model, max_tokens=1000)
        return parse_json_lenient(text), tokens

    result, tokens = retry_call(_call, cfg.get("MAX_RETRY_COUNT", 3))
    result["_tokens"] = tokens
    return result
