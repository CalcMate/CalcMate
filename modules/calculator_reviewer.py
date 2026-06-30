# -*- coding: utf-8 -*-
"""
modules/calculator_reviewer.py — 계산기 AI 검수 (SalaryMate)

흐름: (Claude 생성) → GPT 검수 → PASS(>=80) / REWRITE(<80)
검수 대상: SEO / FAQ / 본문 / 입력폼 / 계산수식 / 결과해설
저장: calculators 테이블에 review_status / review_score / review_reason (+reviewed_at)
      — CalculatorRepository.update_generated 사용(Repository 구조 변경 없음).

함수: review_calculator() / approve() / reject()
"""
import json
from datetime import datetime

from .ai_provider import build_provider_for_role, build_provider
from .utils.parser import parse_json_lenient
from .logger import get_logger, BudgetTracker

LOG = get_logger()
PASS_THRESHOLD = 80
DIMENSIONS = ["seo", "faq", "article", "input_form", "formula", "result_explain"]


def _repo(cfg: dict):
    from adapters.db.factory import get_db_adapter
    from repositories.calculator_repository import CalculatorRepository
    return CalculatorRepository(get_db_adapter(cfg))


def _summary(calc: dict) -> str:
    faq = calc.get("faq")
    if isinstance(faq, str):
        try: faq = json.loads(faq)
        except Exception: faq = []
    return (
        f"계산기명: {calc.get('name','')}\n"
        f"SEO제목: {calc.get('seo_title','')}\n"
        f"메타설명: {calc.get('seo_description', calc.get('seo_desc',''))}\n"
        f"FAQ수: {len(faq) if isinstance(faq, list) else 0}\n"
        f"입력폼/스키마: {calc.get('input_schema','')}\n"
        f"계산수식: {calc.get('formula','')}\n"
        f"본문(앞 1200자): {str(calc.get('article_content',''))[:1200]}"
    )


def review_calculator(cfg: dict, calc: dict) -> dict:
    """계산기 생성물 검수. 반환 {review_score, review_status, review_reason, scores}.
    status: PASS(>=80) / REWRITE(<80)."""
    system = ("너는 콘텐츠 품질 검수자다. 아래 계산기 생성물을 항목(SEO/FAQ/본문/입력폼/계산수식/결과해설)별 "
              "0~100으로 평가하라. AI 티 표현·키워드 스팸·빈약한 정보·수식 오류는 감점. "
              "순수 JSON만 반환: "
              '{"scores":{"seo":0,"faq":0,"article":0,"input_form":0,"formula":0,"result_explain":0},'
              '"total":0,"reason":"100자 이내"}')
    try:
        provider = build_provider(cfg.get("CALC_REVIEW_PROVIDER", "openai"), cfg)
        model    = cfg.get("CALC_REVIEW_MODEL", "gpt-4o")   # 계산기 검수 전용(블로그 editor와 분리)
        text, tokens = provider.chat(system, _summary(calc), model, max_tokens=400)
        try: BudgetTracker(cfg).record(model, tokens)
        except Exception: pass
        d = parse_json_lenient(text)
        scores = d.get("scores", {}) or {}
        total = d.get("total")
        if not isinstance(total, (int, float)) or total == 0:
            vals = [float(scores.get(k, 0)) for k in DIMENSIONS]
            total = round(sum(vals) / len(vals)) if vals else 0
        total = int(round(total))
        status = "PASS" if total >= PASS_THRESHOLD else "REWRITE"
        return {"review_score": total, "review_status": status,
                "review_reason": str(d.get("reason", ""))[:200], "scores": scores}
    except Exception as e:
        LOG.warning("review_calculator 실패→보수적 REWRITE: %s", e)
        return {"review_score": 0, "review_status": "REWRITE",
                "review_reason": f"검수 오류:{e}", "scores": {}}


def approve(cfg: dict, calc_id: str, result: dict):
    """검수 통과 저장(review_status=AUTO_APPROVED 계열). DB는 Repository 경유."""
    _repo(cfg).update_generated(calc_id, {
        "review_status": "AUTO_APPROVED",
        "review_score": result.get("review_score", 0),
        "review_reason": result.get("review_reason", ""),
        "reviewed_at": datetime.now().isoformat(),
    })
    LOG.info("리뷰 APPROVE: %s (%d점)", calc_id, result.get("review_score", 0))


def reject(cfg: dict, calc_id: str, result: dict):
    """검수 미통과 저장(review_status=NEEDS_REVIEW). DB는 Repository 경유."""
    _repo(cfg).update_generated(calc_id, {
        "review_status": "NEEDS_REVIEW",
        "review_score": result.get("review_score", 0),
        "review_reason": result.get("review_reason", ""),
        "reviewed_at": datetime.now().isoformat(),
    })
    LOG.info("리뷰 REJECT(NEEDS_REVIEW): %s (%d점)", calc_id, result.get("review_score", 0))


def review_and_save(cfg: dict, calc: dict) -> dict:
    """검수 후 결과에 따라 자동 approve/reject 저장. 반환: 검수 결과 dict."""
    res = review_calculator(cfg, calc)
    cid = calc.get("id", "")
    if cid:
        (approve if res["review_status"] == "PASS" else reject)(cfg, cid, res)
    return res


def _rewrite(cfg: dict, gen: dict) -> dict:
    """REWRITE 판정 시 텍스트(SEO/FAQ/본문) 재생성. gen을 갱신해 반환."""
    calc = {"name": gen.get("name", ""), "category": gen.get("category", ""),
            "formula": gen.get("formula", ""), "input_schema": gen.get("input_schema", ""),
            "output_schema": gen.get("output_schema", ""),
            "seo_desc": gen.get("seo_description", "")}
    try:
        from .calculator_seo_generator import _seo_pair
        seo = _seo_pair(cfg, calc)
        gen["seo_title"] = seo["seo_title"]; gen["seo_description"] = seo["seo_description"]
    except Exception as e:
        LOG.warning("_rewrite SEO 실패: %s", e)
    try:
        from .calculator_faq_generator import generate_faq
        gen["faq"] = generate_faq(cfg, calc)
    except Exception as e:
        LOG.warning("_rewrite FAQ 실패: %s", e)
    try:
        from .calculator_content_generator import generate_article
        faq = gen.get("faq")
        if isinstance(faq, str):
            try: faq = json.loads(faq)
            except Exception: faq = []
        gen["article_content"] = generate_article(
            cfg, calc, {"seo_title": gen.get("seo_title"),
                        "seo_description": gen.get("seo_description")}, faq)
    except Exception as e:
        LOG.warning("_rewrite 본문 실패: %s", e)
    return gen


def auto_review_and_fix(cfg: dict, gen: dict, max_rewrites: int = 2) -> dict:
    """검수→(REWRITE 시) 자동 재생성 루프→재채점. gen에 review_* 필드 추가하여 반환.
    상태: AUTO_APPROVED / AUTO_REWRITTEN / NEEDS_REVIEW. (사용자 승인 단계 없음)"""
    res = review_calculator(cfg, gen)
    attempts = 0
    if res["review_status"] == "PASS":
        status = "AUTO_APPROVED"
    else:
        status = "NEEDS_REVIEW"
        for _ in range(max_rewrites):
            gen = _rewrite(cfg, gen)
            attempts += 1
            res = review_calculator(cfg, gen)
            if res["review_status"] == "PASS":
                status = "AUTO_REWRITTEN"
                break
    gen.update({
        "review_status": status,
        "review_score": res["review_score"],
        "review_reason": res["review_reason"],
        "review_attempts": attempts,
        "reviewed_at": datetime.now().isoformat(),
    })
    LOG.info("auto_review: %s — %s (%d점, 수정 %d회)",
             gen.get("name", ""), status, res["review_score"], attempts)
    return gen
