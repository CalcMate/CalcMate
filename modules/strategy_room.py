"""
strategy_room.py — PART 3-A: 전략회의실 (v11.6 신규)
"""
import json
from .ai_provider import build_provider, retry_call
from .utils.parser import parse_json_lenient
from .logger import get_logger

LOG = get_logger()

# 하위 호환 별칭 (기존 호출부 보존)
_parse_json_lenient = parse_json_lenient

SYSTEM_STRATEGY = """너는 블로그 자동화 시스템의 전략 분석가다.
최근 7일간 운영 데이터를 분석하고 시스템 성과 개선을 위한 전략 보고서를 작성하라.
⚠️ 역할 경계: 분석 및 추천만 수행. 카테고리 생성, RSS 등록, 링크 삽입 직접 실행 금지.

[AUTO_TOPIC_EXPANSION 전환 가능 여부 판정]
4개 조건 충족 여부를 각각 true/false로 판정. 4개 모두 true면 summary에 반드시 "AUTO_TOPIC_EXPANSION 전환 가능" 포함.

인사말·코드블록 없이 순수 JSON만 반환:
{"new_category_candidates":[],"rss_recommendations":[],"rewrite_candidates":[],"best_publish_time":[],"monetization_suggestions":null,"auto_topic_expansion_eligible":{"condition_1_adsense_post":false,"condition_2_post_count":false,"condition_3_ctr":false,"condition_4_positive_recommendation":false,"all_met":false},"summary":""}"""

def run_strategy_room(analytics: dict, cfg: dict) -> dict:
    if not cfg.get("ENABLE_STRATEGY_ROOM", True):
        return {}
    provider = build_provider(cfg["ORCHESTRATOR_PROVIDER"], cfg)
    model = cfg["MODEL_ORCHESTRATOR"]
    adsense_mode = cfg.get("ADSENSE_MODE", "pre")
    user_msg = (
        f"최근 7일 발행 목록 및 CTR: {json.dumps(analytics.get('recent_posts', []), ensure_ascii=False)}\n"
        f"카테고리별 평균 CTR: {json.dumps(analytics.get('category_ctr', {}), ensure_ascii=False)}\n"
        f"발행 시간대별 성과: {json.dumps(analytics.get('time_slots', {}), ensure_ascii=False)}\n"
        f"현재 RSS 수집원: {cfg.get('RSS_SOURCE_LIST', [])}\n"
        f"발행완료 총 게시물 수: {analytics.get('total_published', 0)}\n"
        f"저성과 목록(30일 경과): {json.dumps(analytics.get('low_ctr_posts', []), ensure_ascii=False)}\n"
        f"ADSENSE_MODE: {adsense_mode}\n"
        f"MIN_POST_COUNT: {cfg.get('MIN_POST_COUNT_FOR_NEW_CATEGORY', 10)}\n"
        f"MIN_CTR: {cfg.get('MIN_CTR_FOR_CATEGORY_EXPANSION', 3.0)}\n"
        f"{'수익화 추천 활성화됨' if adsense_mode == 'post' else '수익화 추천 비활성화(ADSENSE_MODE=pre)'}"
    )
    def _call():
        text, tokens = provider.chat(SYSTEM_STRATEGY, user_msg, model, max_tokens=2000)
        return _parse_json_lenient(text), tokens
    try:
        result, tokens = retry_call(_call, 2)
        result["_tokens"] = tokens
        return result
    except Exception as e:
        LOG.warning("전략회의실 실행 실패 (메인 파이프라인 영향 없음): %s", e,
                    exc_info=(cfg.get("LOG_LEVEL", "INFO") == "DEBUG"))
        return {}
