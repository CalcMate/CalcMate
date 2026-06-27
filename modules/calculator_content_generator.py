# -*- coding: utf-8 -*-
"""
modules/calculator_content_generator.py — 계산기 블로그 본문 생성 + 전체 자동생성 (SalaryMate)

generate_article(): 서론→설명→계산방법→예시→주의사항→FAQ→CTA 구조, 2000자+ HTML
auto_generate_all(): SEO→FAQ→본문→이미지프롬프트→DB저장(Repository) 일괄 실행

모델 규칙: 본문=MODEL_WRITER, (선택)검수=MODEL_EDITOR. 데이터 저장은 Repository 경유.
"""
import json
from datetime import datetime

from .ai_provider import build_provider_for_role, retry_call
from .logger import get_logger, BudgetTracker
from . import calculator_prompt_manager as PM
from . import cleaner
from .calculator_seo_generator import _seo_pair
from .calculator_faq_generator import generate_faq
from .calculator_image_prompt_generator import _image_pair

LOG = get_logger()


def generate_article(cfg: dict, calc: dict, seo: dict = None, faq: list = None,
                     review: bool = False) -> str:
    """블로그 본문 HTML 생성(2000자+). review=True면 Editor 검수 1회."""
    system, user = PM.get_article_prompt(calc, seo, faq)
    provider, model = build_provider_for_role("writing", cfg)   # MODEL_WRITER

    def _call():
        return provider.chat(system, user, model, max_tokens=4000)

    text, tokens = retry_call(_call, cfg.get("MAX_RETRY_COUNT", 3))
    try:
        BudgetTracker(cfg).record(model, tokens)
    except Exception as _e:
        LOG.warning("토큰 비용 기록 실패: %s", _e)
    html = cleaner.parse_html_body(text)

    if review:
        try:
            rprov, rmodel = build_provider_for_role("review", cfg)  # MODEL_EDITOR
            rtext, rtok = rprov.chat(
                "다음 HTML 글의 문법/가독성을 다듬되 구조와 분량을 유지하라. "
                "AI 티 표현 금지. [BODY_HTML_START]...[BODY_HTML_END]로 감싸 반환.",
                html, rmodel, max_tokens=4000)
            try:
                BudgetTracker(cfg).record(rmodel, rtok)
            except Exception:
                pass
            html = cleaner.parse_html_body(rtext) or html
        except Exception as e:
            LOG.warning("본문 검수 실패(무시): %s", e)
    return html


def auto_generate_all(cfg: dict, calc: dict, save: bool = True, review: bool = False,
                      auto_review: bool = True) -> dict:
    """전체 자동 생성: SEO→FAQ→본문→이미지프롬프트→(AI Reviewer 검수/자동수정)→DB저장.
    calc는 calculators 행(dict, 'id' 포함). 반환: 생성 결과 dict(review_* 포함).
    auto_review=True면 calculator_reviewer로 검수 후 REWRITE 시 자동 재생성."""
    name = calc.get("name", "")
    LOG.info("[auto-gen] 시작: %s", name)

    # 1) SEO
    try:
        seo = _seo_pair(cfg, calc)
    except Exception as e:
        LOG.warning("[auto-gen] SEO 실패→기본값: %s", e)
        seo = {"seo_title": f"{datetime.now().year} {name} | 자동 계산",
               "seo_description": f"{name} 계산 방법과 기준을 확인하세요."}

    # 2) FAQ
    faq = generate_faq(cfg, calc)

    # 3) 본문
    article = generate_article(cfg, calc, seo, faq, review=review)

    # 4) 이미지 프롬프트
    img = _image_pair(cfg, calc)

    # 5) AI Reviewer 자동 검수/수정 (REWRITE 시 SEO/FAQ/본문 재생성)
    review_fields = {}
    if auto_review:
        try:
            from .calculator_reviewer import auto_review_and_fix
            gen = {
                "id": calc.get("id", ""), "name": name, "category": calc.get("category", ""),
                "formula": calc.get("formula", ""),
                "input_schema": calc.get("input_schema", ""),
                "output_schema": calc.get("output_schema", ""),
                "seo_title": seo["seo_title"], "seo_description": seo["seo_description"],
                "faq": faq, "article_content": article,
            }
            gen = auto_review_and_fix(cfg, gen)
            # 검수/수정 결과 반영
            seo = {"seo_title": gen["seo_title"], "seo_description": gen["seo_description"]}
            faq = gen["faq"]; article = gen["article_content"]
            review_fields = {k: gen[k] for k in
                             ("review_status", "review_score", "review_reason",
                              "review_attempts", "reviewed_at") if k in gen}
        except Exception as e:
            LOG.warning("[auto-gen] 리뷰어 연결 실패(생성물은 유지): %s", e)

    result = {
        "seo_title": seo["seo_title"],
        "seo_description": seo["seo_description"],
        "seo_desc": seo["seo_description"],   # 기존 컬럼 호환
        "faq": json.dumps(faq, ensure_ascii=False),
        "article_content": article,
        "image_prompt_thumbnail": img["thumbnail"],
        "image_prompt_body": img["body"],
    }
    result.update(review_fields)   # review_status/score/reason/attempts/reviewed_at

    # 6) DB 저장 (Repository 경유)
    if save and calc.get("id"):
        try:
            from adapters.db.factory import get_db_adapter
            from repositories.calculator_repository import CalculatorRepository
            CalculatorRepository(get_db_adapter(cfg)).update_generated(calc["id"], result)
            LOG.info("[auto-gen] 저장 완료: %s", name)
            result["_saved"] = True
        except Exception as e:
            LOG.error("[auto-gen] 저장 실패(시트 권한 확인): %s", e)
            result["_saved"] = False
            result["_save_error"] = str(e)
    return result
