#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/diag_g5.py — G5 실패 원인 통계 진단 스크립트 (진단 전용, 발행 없음)

Phase 1 (AI 호출 없음):
  내부링크 엔진 결과만 확인 → 가설 B(내부링크 부족) 판별
Phase 2 (AI 호출 있음, Phase 1 통과 시):
  writer 1회 실행 후 check_gates → 가설 A(href="#") 판별
"""
import sys
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from modules.config_loader import load_config
from modules.publish_quality import _count_dead_links, _count_internal_links, check_gates
from modules.internal_link_engine import (
    generate_related_calculators, generate_related_articles, inject_internal_links
)
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

# 오늘 G5 실패 확인된 계산기/키워드 조합
TARGETS = [
    ("calc_20260702221622_621a", "주휴수당 계산법"),
    ("calc_20260702221622_621a", "주휴수당 계산 방법"),
    ("calc_20260702221622_621a", "주휴수당 계산"),
    ("calc_20260702221622_621a", "주휴수당 조건"),
    ("calc_20260702221624_38e4", "퇴직금 계산법"),
    ("calc_20260702221624_38e4", "퇴직금 계산 방법"),
    ("calc_20260702221626_303c", "연차수당 계산법"),
    ("calc_20260702221626_303c", "연차수당 계산 방법"),
    ("calc_20260702221627_1cf0", "실업급여 계산법"),
    ("calc_20260702221629_f9fa", "4대보험 계산법"),
]


def phase1_internal_links(cfg: dict) -> list:
    """Phase 1: 내부링크 엔진만 실행 (AI 호출 없음)."""
    print("\n=== Phase 1: 내부링크 엔진 결과 ===")
    results = []
    for cid, keyword in TARGETS:
        rel_calc = generate_related_calculators(cfg, cid, 3)
        rel_art = generate_related_articles(cfg, keyword, 3)

        # 유효 링크 개수 계산 (inject_internal_links와 동일 로직)
        valid_calcs = [c for c in rel_calc if c.get("name") and c.get("url")]
        valid_arts = [a for a in rel_art if a.get("title") and a.get("url")]

        # 실제 주입 결과로 검증
        injected = inject_internal_links("<p>dummy</p>", rel_calc, rel_art)
        has_block = '<div class="internal-links">' in injected
        link_count = _count_internal_links(injected)

        row = {
            "cid": cid,
            "keyword": keyword,
            "valid_calcs": len(valid_calcs),
            "valid_arts": len(valid_arts),
            "link_count": link_count,
            "has_block": has_block,
        }
        results.append(row)
        verdict = "B(내부링크 부족)" if link_count < 2 else "내부링크 OK → Phase2 필요"
        print(f"  [{keyword}] calcs={len(valid_calcs)} arts={len(valid_arts)} "
              f"injected={link_count}개 → {verdict}")

    return results


def phase2_writer_check(cfg: dict, phase1_results: list) -> list:
    """Phase 2: 내부링크가 충분한 케이스만 writer 실행 후 check_gates."""
    needs_phase2 = [r for r in phase1_results if r["link_count"] >= 2]
    if not needs_phase2:
        print("\n=== Phase 2: 전건 내부링크 부족 → Phase 2 불필요 ===")
        return []

    print(f"\n=== Phase 2: writer 실행 ({len(needs_phase2)}건, AI 호출 있음) ===")
    from modules.calculator_pipeline import (
        _write_article, _load_prompt, run_calculator_once
    )
    from modules.calculator_seo_generator import generate_seo
    from modules.calculator_faq_generator import generate_faq

    db = get_db_adapter(cfg)
    calc_repo = CalculatorRepository(db)

    results = []
    for r in needs_phase2:
        cid, keyword = r["cid"], r["keyword"]
        calc = calc_repo.get_by_id(cid)
        if not calc:
            print(f"  [{keyword}] 계산기 조회 실패 — 스킵")
            continue

        seo = generate_seo(cfg, calc.get("name", keyword), keyword)
        try:
            faq = generate_faq(cfg, calc, keyword)
        except Exception:
            faq = []

        # 내부링크 사전 계산
        rel_calc = generate_related_calculators(cfg, cid, 3)
        rel_art = generate_related_articles(cfg, keyword, 3)

        # writer 1회만 실행
        body_html, _ = _write_article(cfg, calc, keyword, seo, faq)

        # assemble final_html
        from modules.app_generator import generate_calculator, render_inline_calculator
        widget_cfg = dict(cfg)
        widget_cfg.update({"SHOW_ARTICLE": False, "SHOW_FAQ": False,
                           "SHOW_RELATED": False, "SHOW_ADSENSE": False,
                           "SHOW_CPA": False, "SHOW_PWA": False})
        widget = render_inline_calculator(generate_calculator(calc, widget_cfg))
        CTA_TEXT = "아래 SalaryMate 계산기를 이용하면 자동으로 계산할 수 있습니다."
        fh = f"{body_html}\n<hr/>\n<h2>계산기 사용하기</h2>\n<p>{CTA_TEXT}</p>\n{widget}"
        final_html = inject_internal_links(fh, rel_calc, rel_art)

        # G5 관련 수치만 직접 계산 (check_gates 전체 미실행 — 비용 절감)
        dead = _count_dead_links(final_html)
        internal = _count_internal_links(final_html)
        min_int = cfg.get("QUALITY_GATE", {}).get("MIN_INTERNAL_LINKS", 2)

        if dead > 0:
            verdict = f"A(href=\"#\" 데드링크 {dead}개)"
        elif internal < min_int:
            verdict = f"B(내부링크 {internal}개 < {min_int})"
        else:
            verdict = "G5 통과"

        print(f"  [{keyword}] dead={dead} internal={internal} → {verdict}")
        results.append({**r, "dead": dead, "internal_final": internal, "verdict": verdict})

    return results


def print_summary(phase1: list, phase2: list) -> None:
    print("\n" + "=" * 60)
    print("G5 실패 원인 통계 (10건)")
    print("=" * 60)

    count_a, count_b, count_ok = 0, 0, 0
    print(f"\n{'키워드':<20} {'calcs':>6} {'arts':>5} {'injected':>9} {'dead':>5} {'verdict'}")
    print("-" * 70)
    for r in phase1:
        p2 = next((x for x in phase2 if x["cid"] == r["cid"] and x["keyword"] == r["keyword"]), None)
        if p2:
            dead = p2.get("dead", 0)
            verdict = p2.get("verdict", "?")
        elif r["link_count"] < 2:
            dead = "-"
            verdict = f"B(내부링크 {r['link_count']}개)"
        else:
            dead = "-"
            verdict = "Phase2 미실행"

        print(f"  {r['keyword']:<20} {r['valid_calcs']:>5} {r['valid_arts']:>5} "
              f"{r['link_count']:>9} {str(dead):>5}  {verdict}")

        if "A" in str(verdict):
            count_a += 1
        elif "B" in str(verdict):
            count_b += 1
        elif verdict == "G5 통과":
            count_ok += 1

    print("-" * 70)
    total = len(phase1)
    print(f"\n  가설 A (href=\"#\" 데드링크): {count_a}건 / {total}건")
    print(f"  가설 B (내부링크 부족):      {count_b}건 / {total}건")
    print(f"  G5 통과 (기타 원인):         {count_ok}건 / {total}건")
    print(f"  미확정:                       {total - count_a - count_b - count_ok}건 / {total}건")

    if count_b > count_a:
        print("\n결론: 가설 B(내부링크 부족)가 지배적 원인")
    elif count_a > count_b:
        print("\n결론: 가설 A(href=\"#\" 데드링크)가 지배적 원인")
    else:
        print("\n결론: 미확정 — 추가 분석 필요")


if __name__ == "__main__":
    cfg = load_config()
    p1 = phase1_internal_links(cfg)
    p2 = phase2_writer_check(cfg, p1)
    print_summary(p1, p2)
