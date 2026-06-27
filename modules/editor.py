"""
editor.py — M4 Review AI (Claude Sonnet)
STEP 8: 팩트 검증 / 중복 제거 / 가독성 향상 / SEO 검수 / 품질 통과 판정

AI 역할 정의서:
  담당: Claude Sonnet (review_ai)
  config 키: review_ai (sites 탭)
  출력: 수정 완료 HTML [BODY_HTML_START]...[BODY_HTML_END]
"""
from .ai_provider import build_provider_for_role, retry_call
from .telegram_notifier import send as tg_send

# ── M4 Review AI 시스템 프롬프트 ─────────────────────────────────────────────
SYSTEM_M4_PRE = """너는 수석 편집자다.

입력된 HTML을 검토하여
중복 제거 / 가독성 향상 / SEO 개선 / 사실관계 검증을 수행한다.

원본 구조는 유지한다.
필요한 부분만 수정한다.
수정 완료 HTML만 출력한다.

[애드센스 승인 전 필터 규칙]
1. 공백 제외 2,500자 이상 3,500자 이하
2. "~이다","~함이 바람직하다","~로 규정되어 있다" 등 객관적 서술어로 문미 통일
3. H2/H3 계층구조 준수
4. AI 패턴 단어 완전 제거:
   "먼저","다음으로","결론적으로","꼭 확인하세요","놓치지 마세요"

인사말 없이 [BODY_HTML_START]...[BODY_HTML_END] 내에 순수 HTML만 출력."""

SYSTEM_M4_POST = """너는 수석 편집자다.

입력된 HTML을 검토하여
중복 제거 / 가독성 향상 / SEO 개선 / 사실관계 검증을 수행한다.

원본 구조는 유지한다.
필요한 부분만 수정한다.
수정 완료 HTML만 출력한다.

[애드센스 승인 후 필터 규칙]
1. 공백 제외 2,000자 이상 3,000자 이하
2. 도입부에 대상자 현실 고충 공감 스토리텔링 삽입
3. 친근한 구어체로 변환. 핵심 금액·마감일에 <strong> 태그
4. 3~4문장 단위 문단 분리 (모바일 최적화)
5. AI 패턴 표현 10가지 완전 제거
6. 아웃바운드 링크·내부링크 블록 HTML 훼손 금지

인사말 없이 [BODY_HTML_START]...[BODY_HTML_END] 내에 순수 HTML만 출력."""


def edit(draft_html: str, cfg: dict, logger=None,
         site_cfg: dict = None) -> tuple[str, int]:
    """
    M4 Review AI 호출.
    site_cfg 있으면 해당 사이트의 review_ai 프로필 사용.
    실패 시 fallback 모델로 재시도.
    """
    mode = cfg.get("ADSENSE_MODE", "pre")
    system = SYSTEM_M4_PRE if mode == "pre" else SYSTEM_M4_POST

    # 1차: 주 모델 (review_ai 프로필)
    try:
        provider, model = build_provider_for_role("review", cfg, site_cfg)

        def _call():
            return provider.chat(system, draft_html, model, max_tokens=4000)

        return retry_call(_call, cfg.get("MAX_RETRY_COUNT", 3))

    except Exception as e:
        if logger:
            logger.warning(f"[M4] 주 모델 실패: {e} → fallback 시도")
        tg_send(cfg, f"⚠️ M4 Review AI 실패: {e} — fallback 전환")

    # 2차: fallback (EDITOR_FALLBACK_PROVIDER)
    try:
        from .ai_provider import build_provider
        fb_provider = build_provider(
            cfg.get("EDITOR_FALLBACK_PROVIDER", "openai"), cfg)
        fb_model = cfg.get("MODEL_EDITOR_FALLBACK", "gpt-4o")

        def _fb_call():
            return fb_provider.chat(system, draft_html, fb_model, max_tokens=4000)

        return retry_call(_fb_call, 2)

    except Exception as e2:
        if logger:
            logger.error(f"[M4] fallback도 실패: {e2}")
        raise
