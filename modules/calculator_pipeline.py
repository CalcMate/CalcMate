# -*- coding: utf-8 -*-
"""
modules/calculator_pipeline.py — 계산기 콘텐츠 파이프라인 (v12.0)

흐름: Calculator(DB) → Keyword(Collector) → 점수(strategist_calculator)
      → SEO/FAQ 생성 → SEO 블로그 글 작성(calculator_writer_prompt)
      → 계산기 위젯(template_engine) CTA 삽입 → ArticleRepository 저장 → 발행

기존 run_once(정책/RSS)와 분리된 별도 경로. 모든 데이터 접근 Repository/Adapter 경유.
"""
import json
import time
from datetime import datetime
from pathlib import Path

from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository
from repositories.article_repository import ArticleRepository
from .collector.factory import get_collector
from .ai_roles import make_provider
from .calculator_seo_generator import generate_seo
from .calculator_faq_generator import generate_faq
from .strategist_calculator import score_keywords
from . import cleaner
from . import publisher
from .logger import get_logger, BudgetTracker
from . import telegram_notifier as tg

LOG = get_logger()
_PROMPT = Path(__file__).resolve().parent.parent / "prompts" / "calculator_writer_prompt.txt"

CTA_TEXT = "아래 SalaryMate 계산기를 이용하면 자동으로 계산할 수 있습니다."


def _load_prompt() -> str:
    try:
        return _PROMPT.read_text(encoding="utf-8")
    except Exception:
        return ("너는 SEO 에디터다. 주어진 키워드로 2500~3500자 한국어 블로그 글을 작성하라. "
                "계산기 CTA/위젯은 시스템이 본문 뒤에 자동 삽입한다. "
                "[BODY_HTML_START]...[BODY_HTML_END]로 감싸라.")


def _write_article(cfg: dict, calc: dict, keyword: str, seo: dict, faq: list) -> tuple:
    provider, model = make_provider(cfg, "writer")
    system = _load_prompt()
    user = (
        f"계산기명: {calc.get('name')}\n"
        f"타겟 키워드(글 주제): {keyword}\n"
        f"SEO 제목: {seo.get('seo_title')}\n"
        f"메타설명: {seo.get('seo_description')}\n"
        f"계산 공식: {calc.get('formula','')}\n"
        f"FAQ: {json.dumps(faq, ensure_ascii=False)}"
        # CTA/위젯은 시스템이 본문 뒤에 자동 삽입하므로 AI 본문에 CTA를 요구하지 않는다(중복 방지).
    )
    text, tokens = provider.chat(system, user, model, max_tokens=3500)
    try:
        BudgetTracker(cfg).record(model, tokens)
    except Exception as _e:
        LOG.warning("토큰 비용 기록/조회 실패: %s", _e)
    return cleaner.parse_html_body(text), tokens


def run_calculator_once(cfg: dict, max_count: int = None) -> dict:
    """활성 계산기 키워드로 SEO 글을 생산/발행. max_count 미지정 시 DAILY_POST_COUNT."""
    start = time.time()
    budget = BudgetTracker(cfg)
    target = int(max_count if max_count is not None else cfg.get("DAILY_POST_COUNT", 1) or 1)

    bs = budget.check_budget()
    if bs["daily_exceeded"] or bs["monthly_exceeded"]:
        LOG.warning("예산 초과 — 계산기 파이프라인 중단")
        return {"produced": 0, "reason": "budget"}

    # 1) 키워드 수집 (Calculator Collector)
    items = get_collector("calculator").collect(cfg, site=None)
    if not items:
        LOG.info("활성 계산기 없음 — 종료 (Calculator Builder/시드로 등록 필요)")
        return {"produced": 0, "reason": "no_calculators"}

    # 2) 점수화/정렬 (기본 휴리스틱 — 비용 0, cfg.CALCULATOR_AI_SCORE=true면 AI)
    use_ai = bool(cfg.get("CALCULATOR_AI_SCORE", False))
    ranked = score_keywords(cfg, items, use_ai=use_ai)
    LOG.info("계산기 키워드 %d개 수집/정렬 (상위 점수 %s)", len(ranked),
             ranked[0].get("score") if ranked else "-")

    # 중복 방지용 기존 제목
    repo = CalculatorRepository(get_db_adapter(cfg))
    art_repo = ArticleRepository(get_db_adapter(cfg))
    try:
        existing = set(art_repo.get_recent_published_titles(50))
    except Exception:
        existing = set()

    stats = {"produced": 0, "processed": 0, "failed": 0, "no_wp": 0, "dup": 0}
    for it in ranked:
        if stats["produced"] >= target:
            break
        keyword = it.get("keyword") or it.get("title", "")
        calc = repo.get_by_id(it.get("calculator_id", "")) or {"name": keyword}
        stats["processed"] += 1
        try:
            # 계산기당 발행 상한(설정값) — 상태 판단은 Repository(count_active_articles)에 위임.
            # 파이프라인은 개수만 비교하고 상태값 문자열을 직접 다루지 않는다.
            cid = it.get("calculator_id", "")
            max_per = int(cfg.get("MAX_ARTICLES_PER_CALCULATOR", 1) or 1)
            if cid and art_repo.count_active_articles(cid) >= max_per:
                stats["dup"] += 1
                continue
            seo = generate_seo(cfg, calc.get("name", keyword), keyword)
            if seo.get("seo_title") in existing:
                stats["dup"] += 1
                continue
            # FAQ: 계산기에 저장된 것 우선, 없으면 생성
            faq = []
            if calc.get("faq"):
                try:
                    faq = json.loads(calc["faq"]) if isinstance(calc["faq"], str) else calc["faq"]
                except Exception:
                    faq = []
            if not faq:
                faq = generate_faq(cfg, calc.get("name", keyword))

            body_html, _ = _write_article(cfg, calc, keyword, seo, faq)
            # 계산기 위젯: app_generator(v2)로 실제 formula/퇴직금 날짜로직 반영(구 naive 합산 제거).
            # 블로그 본문과 중복되는 섹션(본문/FAQ/관련계산기/광고/PWA)은 위젯에서 숨김.
            from .app_generator import generate_calculator, render_inline_calculator
            widget_cfg = dict(cfg)
            widget_cfg.update({"SHOW_ARTICLE": False, "SHOW_FAQ": False, "SHOW_RELATED": False,
                               "SHOW_ADSENSE": False, "SHOW_CPA": False, "SHOW_PWA": False})
            widget = render_inline_calculator(generate_calculator(calc, widget_cfg))
            final_html = (f"{body_html}\n<hr/>\n<h2>계산기 사용하기</h2>\n"
                          f"<p>{CTA_TEXT}</p>\n{widget}")
            # 내부링크: 관련 계산기/관련 글 자동 연결 (신규)
            try:
                from .internal_link_engine import (generate_related_calculators,
                                                   generate_related_articles, inject_internal_links)
                rel_calc = generate_related_calculators(cfg, it.get("calculator_id", ""), 3)
                rel_art = generate_related_articles(cfg, keyword, 3)
                final_html = inject_internal_links(final_html, rel_calc, rel_art)
            except Exception as _e:
                LOG.warning("내부링크 생성 실패(무시): %s", _e)

            # 발행
            pub = publisher.publish(datetime.now().strftime("%Y%m%d%H%M%S"),
                                    {"seo_title": seo.get("seo_title"),
                                     "meta_description": seo.get("seo_description"),
                                     "tags_list": seo.get("seo_keywords", [])},
                                    final_html, {}, cfg)
            pub_status = pub.get("status", "published")
            article_id = art_repo.save({
                "정책명": keyword,
                "최종추천제목": seo.get("seo_title"),
                "메타설명": seo.get("seo_description"),
                "태그": ", ".join(seo.get("seo_keywords", []) or []),
                "발행 URL": pub.get("wordpress", ""),
                "wp_post_id": pub.get("wp_post_id", ""),
                "wp_permalink": pub.get("wp_permalink", ""),
                "wp_status": pub.get("wp_status", ""),
                "published_at": pub.get("published_at", ""),
                "발행일시": datetime.now().isoformat(),
                "원본출처": calc.get("published_url", ""),
                "상태값": "발행완료" if pub_status == "published" else "검수대기",
                "site_id": it.get("site_id", ""),
                "calculator_id": cid,
            })
            # history "publish" 이벤트 기록(발행 흐름 무영향 — 실패해도 무시)
            try:
                art_repo.append_history(article_id, "publish", {"wp_post_id": pub.get("wp_post_id", "")})
            except Exception as _e:
                LOG.warning("history(publish) 기록 실패(무시): %s", _e)
            existing.add(seo.get("seo_title"))
            stats["produced"] += 1
            if pub_status != "published":
                stats["no_wp"] += 1
            LOG.info("계산기 글 생산: %s (%s)", seo.get("seo_title"), pub_status)
        except Exception as e:
            stats["failed"] += 1
            LOG.error("계산기 글 생성 오류(%s): %s", keyword, e, exc_info=True)
            tg.send(cfg, f"❌ 계산기 글 오류: {e}")

    elapsed = round(time.time() - start, 1)
    LOG.info("✅ 계산기 파이프라인 종료: 목표 %d / 생산 %d (발행 %d, WP대기 %d) / 처리 %d / 중복 %d / 실패 %d / %s초",
             target, stats["produced"], stats["produced"] - stats["no_wp"], stats["no_wp"],
             stats["processed"], stats["dup"], stats["failed"], elapsed)
    return stats
