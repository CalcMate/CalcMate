# -*- coding: utf-8 -*-
"""
modules/strategist_calculator.py — 계산기 키워드 점수 평가 (v12.0)

7개 항목(검색의도/CPC/검색량/SEO경쟁도/계산기연결성/전환가능성/시즌성)을
0~100으로 평가하고 최종 0~100 점수를 반환한다.
AI 평가 우선, 실패 시 휴리스틱 fallback.
"""
from .ai_roles import make_provider
from .json_utils import parse_json_lenient
from .logger import get_logger, BudgetTracker

LOG = get_logger()

DIMENSIONS = ["search_intent", "cpc", "search_volume",
              "seo_competition", "calculator_link", "conversion", "seasonality"]

# 휴리스틱용 가점 키워드
_HOT = ("계산법", "계산 방법", "계산", "세금", "지급기준", "조건")


def _heuristic(keyword: str) -> int:
    s = 55
    for h in _HOT:
        if h in keyword:
            s += 7
    if len(keyword) <= 12:
        s += 5
    return max(0, min(100, s))


def score_keyword(cfg: dict, keyword: str, calculator_name: str = "") -> dict:
    system = ("너는 SEO 키워드 평가 전문가다. 아래 항목을 각각 0~100으로 평가하고 "
              "최종 점수(0~100)를 산출하라. 순수 JSON만 반환: "
              '{"scores":{"search_intent":0,"cpc":0,"search_volume":0,"seo_competition":0,'
              '"calculator_link":0,"conversion":0,"seasonality":0},"score":0}')
    user = f"키워드: {keyword}\n관련 계산기: {calculator_name}"
    try:
        provider, model = make_provider(cfg, "orchestrator")
        text, tokens = provider.chat(system, user, model, max_tokens=300)
        try:
            BudgetTracker(cfg).record(model, tokens)
        except Exception as _e:
            LOG.warning("토큰 비용 기록/조회 실패: %s", _e)
        d = parse_json_lenient(text)
        scores = d.get("scores", {})
        final = d.get("score")
        if not isinstance(final, (int, float)) or final == 0:
            vals = [float(scores.get(k, 0)) for k in DIMENSIONS]
            final = round(sum(vals) / len(vals)) if vals else _heuristic(keyword)
        return {"keyword": keyword, "score": int(round(final)), "scores": scores}
    except Exception as e:
        LOG.warning("키워드 점수 평가 실패(%s) → 휴리스틱: %s", keyword, e)
        return {"keyword": keyword, "score": _heuristic(keyword), "scores": {}}


def score_keywords(cfg: dict, items: list, calculator_name: str = "",
                   use_ai: bool = True) -> list:
    """items: [{keyword/title,...}] → 점수 부여 후 내림차순 정렬.
    use_ai=False면 휴리스틱만(비용 0)."""
    out = []
    for it in items:
        kw = it.get("keyword") or it.get("title", "")
        if not kw:
            continue
        if use_ai:
            sc = score_keyword(cfg, kw, calculator_name or it.get("calculator_id", ""))
        else:
            sc = {"keyword": kw, "score": _heuristic(kw), "scores": {}}
        merged = dict(it)
        merged.update(sc)
        out.append(merged)
    out.sort(key=lambda x: x.get("score", 0), reverse=True)
    return out
