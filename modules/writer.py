"""
writer.py — M3 Writer AI (GPT)
STEP 7: 본문 초안 작성 + SEO 최적화 HTML 생성

AI 역할 정의서:
  담당: GPT (gpt-4o)
  config 키: writing_ai (sites 탭)
  출력: [BODY_HTML_START]...[BODY_HTML_END]
"""
from .ai_provider import build_provider_for_role, retry_call

# ── M3 Writer AI 시스템 프롬프트 ─────────────────────────────────────────────
SYSTEM_M3_POLICY = """너는 10년차 SEO 콘텐츠 에디터다.

입력된 키워드 / FAQ / 콘텐츠 구조를 기반으로
검색엔진 친화적이고 사용자 친화적인 콘텐츠를 작성한다.

AI 티가 나는 문체를 사용하지 않는다.
과도한 반복을 금지한다.
HTML 형식으로만 출력한다.

[역할 경계]
정보 구조 설계 및 초안 HTML 작성만 수행. 어조 교정은 후속 에이전트 담당.

[본문 구조 — H2 순서 필수 준수]
1. 이 정책이란? (개요+배경)
2. 지원 대상 (자격 조건 상세)
3. 지원 내용 (혜택/금액/서비스)
4. 신청 방법 및 절차 (단계별 번호 리스트)
5. 신청 기간 및 마감일 (날짜 강조)
6. 유의사항 및 자주 묻는 질문 (FAQ 2~3개)
7. [내부링크 블록] — 관련글 존재 시만
8. [출처 블록] — 항상

[금지 표현]
"먼저","다음으로","결론적으로","꼭 확인하세요","놓치지 마세요",
"안녕하세요","오늘은","지금 바로","여러분"

완성 HTML을 반드시 [BODY_HTML_START]...[BODY_HTML_END] 태그로 감싸라."""

SYSTEM_M3_CALCULATOR = """너는 10년차 SEO 콘텐츠 에디터다.

계산기 및 도구 관련 콘텐츠를 작성한다.
독자가 계산기를 사용하고 결과를 이해하는 데 집중한다.

AI 티가 나는 문체를 사용하지 않는다.
과도한 반복을 금지한다.
HTML 형식으로만 출력한다.

[본문 구조 — H2 순서 필수 준수]
1. [계산기명]이란?
2. 계산 방법 (공식 + 예시)
3. 조건 및 자격
4. 계산 결과 활용법
5. 자주 묻는 질문 (FAQ 3~5개)
6. [관련 계산기 내부링크] — 있을 때만
7. [출처 블록]

완성 HTML을 반드시 [BODY_HTML_START]...[BODY_HTML_END] 태그로 감싸라."""

# source_type → 시스템 프롬프트 매핑
_SYSTEM_MAP = {
    "policy":     SYSTEM_M3_POLICY,
    "calculator": SYSTEM_M3_CALCULATOR,
    "affiliate":  SYSTEM_M3_POLICY,
    "finance":    SYSTEM_M3_POLICY,
}


def write_draft(clean_data: dict, seo_data: dict, strategy: dict,
                related_links: list, cfg: dict,
                site_cfg: dict = None) -> tuple[str, int]:
    """
    M3 Writer AI 호출.
    site_cfg 있으면 해당 사이트의 writing_ai 프로필 사용.
    source_type에 따라 시스템 프롬프트 자동 선택.
    """
    provider, model = build_provider_for_role("writing", cfg, site_cfg)
    source_type = clean_data.get("source_type", "policy")
    system = _SYSTEM_MAP.get(source_type, SYSTEM_M3_POLICY)

    links_info = ""
    if any(related_links):
        links_info = f"관련글링크: {related_links}\n"

    # M1 Research AI 결과 활용 (faq, outline, entities)
    faq_context     = seo_data.get("faq", [])
    outline_context = seo_data.get("outline", [])

    user_msg = (
        f"콘텐츠명: {clean_data.get('clean_policy_name')}\n"
        f"핵심요약: {clean_data.get('clean_summary')}\n"
        f"수혜대상: {clean_data.get('clean_target')}\n"
        f"지원혜택: {clean_data.get('clean_benefit', '')}\n"
        f"신청기간: {clean_data.get('clean_period', '')}\n"
        f"마감일: {clean_data.get('clean_deadline', '')}\n"
        f"원본출처: {clean_data.get('source_url', '')}\n"
        f"SEO제목: {seo_data.get('seo_title')}\n"
        f"메인키워드: {seo_data.get('main_keyword')}\n"
        f"롱테일키워드: {seo_data.get('longtail_keywords', [])}\n"
        f"콘텐츠각도: {strategy.get('content_angle')}\n"
        f"M1 FAQ: {faq_context}\n"
        f"M1 콘텐츠구조: {outline_context}\n"
        f"{links_info}"
    )

    def _call():
        return provider.chat(system, user_msg, model, max_tokens=3000)

    return retry_call(_call, cfg.get("MAX_RETRY_COUNT", 3))
