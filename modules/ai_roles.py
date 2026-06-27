# -*- coding: utf-8 -*-
"""
modules/ai_roles.py — AI 역할 체계 (v12.0 확장)

총괄/리서치/코드/작성/검수/이미지 역할별 provider+model 매핑.
신규 기능(AI Workspace, App Factory, Pipeline Monitor)이 이 역할표를 사용한다.

기존 파이프라인의 ORCHESTRATOR/PLANNER/WRITER/EDITOR 설정은 그대로 유지되며,
이 모듈은 '확장용' 역할표(config.AI_ROLES)로 별도 동작한다(기존 미수정).

※ 모델 ID는 실제 호출 가능한 현재 모델로 둔다(지시서의 'GPT-5.5'는 출시 시
   설정에서 교체. 그 전까지는 최신 GPT로 매핑).
"""
from .ai_provider import build_provider

# 역할 기본 정의 (label/desc는 UI 표기용, provider/model은 실호출용)
# 모델 ID는 현재 키로 실호출 검증된 값으로 둔다(2026-06 기준):
#   claude-sonnet-4-6 (3.5계열 retired), gemini-2.5-flash (2.5-pro는 키 쿼터 429), gpt-4o
ROLE_DEFS = {
    "orchestrator": {"label": "총괄 AI",   "provider": "openai", "model": "gpt-4o",
                     "desc": "전체 의사결정 · 품질 관리 · 작업 분배 · 전략회의실"},
    "research":     {"label": "리서치 AI", "provider": "gemini", "model": "gemini-2.5-flash",
                     "desc": "자료 조사 · 경쟁 분석 · 키워드 분석"},
    "code":         {"label": "코드 AI",   "provider": "claude", "model": "claude-sonnet-4-6",
                     "desc": "HTML · CSS · JS · Python · 대시보드 기능 개발"},
    "writer":       {"label": "작성 AI",   "provider": "openai", "model": "gpt-4o",
                     "desc": "블로그 초안 · FAQ · SEO 생성"},
    "review":       {"label": "검수 AI",   "provider": "openai", "model": "gpt-4o",
                     "desc": "품질검사 · SEO 검수 · 문법 · 중복검사"},
    "image":        {"label": "이미지 AI", "provider": "gemini", "model": "gemini-2.5-flash",
                     "desc": "이미지 프롬프트 생성(실제 렌더링은 Pollinations/image_generator)"},
}
ROLE_KEYS = list(ROLE_DEFS.keys())


def get_role(cfg: dict, role: str) -> tuple:
    """(provider, model) 반환. config.AI_ROLES 우선, 없으면 기본값."""
    base = ROLE_DEFS.get(role, ROLE_DEFS["orchestrator"])
    roles = (cfg.get("AI_ROLES") or {})
    r = roles.get(role, {})
    provider = r.get("provider") or base["provider"]
    model = r.get("model") or base["model"]
    return provider, model


def make_provider(cfg: dict, role: str):
    """역할에 맞는 (provider 인스턴스, model) 반환. ai_provider 경유."""
    provider_name, model = get_role(cfg, role)
    return build_provider(provider_name, cfg), model


def all_roles(cfg: dict) -> dict:
    """현재 적용 중인 역할표 전체 {role: {label,provider,model,desc}}."""
    out = {}
    for k, base in ROLE_DEFS.items():
        prov, model = get_role(cfg, k)
        out[k] = {"label": base["label"], "desc": base["desc"],
                  "provider": prov, "model": model}
    return out
