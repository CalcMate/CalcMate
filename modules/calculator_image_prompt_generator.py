# -*- coding: utf-8 -*-
"""
modules/calculator_image_prompt_generator.py — 이미지 프롬프트 자동 생성 (SalaryMate)
모델 규칙: Gemini Flash(research) 우선, 실패 시 Writer.
함수: generate_thumbnail_prompt() / generate_body_prompt()
"""
from .ai_provider import build_provider_for_role
from .utils.parser import parse_json_lenient
from .logger import get_logger, BudgetTracker
from . import calculator_prompt_manager as PM

LOG = get_logger()

_FALLBACK = {
    "thumbnail": "Minimalist vector illustration for financial calculator, clean flat design, "
                 "professional icon style, soft colors, high quality, no text, no numbers, "
                 "related to salary and working hours",
    "body": "Office workspace, calculator, salary report, business documents, "
            "natural light, realistic photography",
}


def _image_pair(cfg: dict, calc: dict) -> dict:
    """썸네일/본문 프롬프트 1회 생성. Gemini Flash 우선 → 실패 시 Writer."""
    system, user = PM.get_image_prompt(calc)
    # 썸네일 프롬프트 보완: 풍경 금지, 일러스트/아이콘 스타일 강제
    system += "\n[썸네일 규칙] 풍경 사진 절대 금지. 해당 계산기의 핵심 주제를 상징하는 현대적인 일러스트 또는 아이콘 스타일로 생성할 것."
    
    for role in ("research", "writing"):   # research=Gemini Flash, writing=Writer
        try:
            provider, model = build_provider_for_role(role, cfg)
            text, tokens = provider.chat(system, user, model, max_tokens=1500, json_mode=True)
            try:
                BudgetTracker(cfg).record(model, tokens)
            except Exception as _e:
                LOG.warning("토큰 비용 기록 실패: %s", _e)
            d = parse_json_lenient(text)
            return {"thumbnail": d.get("thumbnail") or _FALLBACK["thumbnail"],
                    "body": d.get("body") or _FALLBACK["body"]}
        except Exception as e:
            LOG.warning("이미지 프롬프트 생성 실패(role=%s): %s", role, e)
    return dict(_FALLBACK)


def generate_thumbnail_prompt(cfg: dict, calc: dict) -> str:
    return _image_pair(cfg, calc)["thumbnail"]


def generate_body_prompt(cfg: dict, calc: dict) -> str:
    return _image_pair(cfg, calc)["body"]
