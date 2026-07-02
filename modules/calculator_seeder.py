# -*- coding: utf-8 -*-
"""
modules/calculator_seeder.py — 초기 계산기 데이터 시더 (SalaryMate 확장, 신규)

퇴직금/주휴수당/실업급여/연차수당/4대보험 5종을 calculators 시트에 등록.
기본 SEO/FAQ/스키마/수식 포함. Repository 경유(직접 Sheets 접근 금지). 멱등(이름 중복 스킵).

지시서 요구 함수: seed_default_calculators()
기존 calculator_seed.SAMPLE_CALCULATORS 를 재사용하여 데이터 단일 출처 유지.
"""
import json

from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository
from .calculator_seed import SAMPLE_CALCULATORS
from .logger import get_logger

LOG = get_logger()

# 기본 수식(formula_engine 규격) — SAMPLE_CALCULATORS slug 기준 매핑
DEFAULT_FORMULAS = {
    "severance-pay":            "avg_monthly_wage * (total_days / 365)",          # 퇴직금(입사일~퇴사일 → total_days)
    "weekly-holiday-allowance": "hourly_wage*(weekly_hours/40*8)",                # 주휴수당(주40h 기준 1일)
    "annual-leave-allowance":   "daily_wage*unused_days",                         # 연차수당
    "unemployment-benefit":     "avg_daily_wage*0.6",                             # 실업급여 1일
    "four-insurances":          {"national_pension": "monthly_salary*0.045",
                                 "health_insurance": "monthly_salary*0.03545",
                                 "employment_insurance": "monthly_salary*0.009",
                                 "total": "monthly_salary*(0.045+0.03545+0.009)"},
}


def seed_default_calculators(cfg: dict) -> dict:
    """초기 5종 등록(멱등). 반환: {'created': n, 'skipped': m, 'names': [...]}"""
    repo = CalculatorRepository(get_db_adapter(cfg))
    try:
        existing = {str(c.get("name", "")).strip() for c in repo.get_all()}
    except Exception as e:
        LOG.error("계산기 조회 실패(시트 권한 확인): %s", e)
        return {"created": 0, "skipped": 0, "error": str(e)}

    created, skipped, names = 0, 0, []
    for c in SAMPLE_CALCULATORS:
        if c["name"] in existing:
            skipped += 1
            continue
        formula = DEFAULT_FORMULAS.get(c["slug"], "")
        repo.upsert_by_slug({
            "name": c["name"], "slug": c["slug"], "category": c["category"],
            "calculator_type": c["calculator_type"],
            "seo_title": c["seo_title"], "seo_desc": c["seo_desc"],
            "formula": formula if isinstance(formula, str) else json.dumps(formula, ensure_ascii=False),
            "faq": json.dumps(c["faq"], ensure_ascii=False),
            "input_schema": json.dumps(c["input_schema"], ensure_ascii=False),
            "output_schema": json.dumps(c["output_schema"], ensure_ascii=False),
            "status": "active",
        })
        created += 1
        names.append(c["name"])
    LOG.info("기본 계산기 시드: 생성 %d / 스킵 %d", created, skipped)
    return {"created": created, "skipped": skipped, "names": names}
