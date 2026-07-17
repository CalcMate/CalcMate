# -*- coding: utf-8 -*-
"""
modules/calculator_seo_generator.py — 계산기 SEO 메타 자동 생성 (v12.0)
출력: seo_title / seo_description / seo_keywords
"""
from datetime import datetime

from .ai_roles import make_provider
from .ai_provider import build_provider_for_role
from .utils.parser import parse_json_lenient
from .logger import get_logger, BudgetTracker
from . import calculator_prompt_manager as PM

LOG = get_logger()


def _seo_pair(cfg: dict, calc: dict) -> dict:
    """calc dict 기반 SEO 1회 생성(제목+메타). 모델 규칙: MODEL_WRITER."""
    system, user = PM.get_seo_prompt(calc)
    provider, model = build_provider_for_role("writing", cfg)
    text, tokens = provider.chat(system, user, model, max_tokens=400)
    try:
        BudgetTracker(cfg).record(model, tokens)
    except Exception as _e:
        LOG.warning("토큰 비용 기록 실패: %s", _e)
    d = parse_json_lenient(text)
    name = calc.get("name", "")
    return {
        "seo_title": d.get("seo_title") or f"{datetime.now().year} {name} | 자동 계산",
        "seo_description": d.get("seo_description")
        or f"{name.replace('계산기','').strip()} 계산 방법과 기준을 확인하고 자동 계산기를 이용해보세요.",
    }


def generate_seo_title(cfg: dict, calc: dict) -> str:
    """SEO 제목 생성(지시서 함수). calc dict 입력."""
    try:
        return _seo_pair(cfg, calc)["seo_title"]
    except Exception as e:
        LOG.warning("SEO 제목 생성 실패 → 기본값: %s", e)
        return f"{datetime.now().year} {calc.get('name','')} | 자동 계산"


def generate_meta_description(cfg: dict, calc: dict) -> str:
    """SEO 메타설명 생성(지시서 함수). calc dict 입력."""
    try:
        return _seo_pair(cfg, calc)["seo_description"]
    except Exception as e:
        LOG.warning("메타설명 생성 실패 → 기본값: %s", e)
        base = calc.get("name", "").replace("계산기", "").strip()
        return f"{base} 계산 방법과 기준을 확인하고 자동 계산기로 즉시 계산해보세요."


def generate_seo(cfg: dict, name: str, keyword: str = "") -> dict:
    year = datetime.now().year
    system = ("너는 SEO 전문가다. 주어진 계산기/키워드에 대한 SEO 메타데이터를 작성하라. "
              "규칙: "
              "1) seo_title은 28~40자, 연도 포함. "
              "2) 타겟 키워드를 제목에 반드시 포함할 것(예: '계산법' 키워드면 '계산법'이 제목에 있어야 함). "
              "3) 서로 다른 키워드는 반드시 서로 다른 제목을 만들 것 — '총정리/가이드/안내' 등 동일 suffix로 수렴 금지. "
              "순수 JSON만 반환: "
              '{"seo_title":"","seo_description":"","seo_keywords":[]}')
    user = f"계산기명: {name}\n타겟 키워드: {keyword or name}\n연도: {year}"
    try:
        provider, model = make_provider(cfg, "writer")
        text, tokens = provider.chat(system, user, model, max_tokens=500)
        try:
            BudgetTracker(cfg).record(model, tokens)
        except Exception as _e:
            LOG.warning("토큰 비용 기록/조회 실패: %s", _e)
        d = parse_json_lenient(text)
        return {
            "seo_title": d.get("seo_title", "") or f"{year} {name} | 자동 계산",
            "seo_description": d.get("seo_description", ""),
            "seo_keywords": d.get("seo_keywords", []),
        }
    except Exception as e:
        LOG.warning("SEO 생성 실패(%s) → 기본값: %s", name, e)
        base = name.replace("계산기", "").strip()
        return {
            "seo_title": f"{year} {name} | 자동 계산",
            "seo_description": f"{base} 지급 기준과 계산 방법을 확인하고 자동 계산기를 이용해보세요.",
            "seo_keywords": [keyword or name, f"{base} 계산", f"{base} 계산법"],
        }
