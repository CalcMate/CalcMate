# -*- coding: utf-8 -*-
"""
scripts/phase5_2b_regen_verify.py — Phase 5-2-B 대표 샘플 5개 재생성 + Gate 검증

실행: python scripts/phase5_2b_regen_verify.py
결과: data/workspace/phase5_2b/ 폴더에 HTML + JSON 결과 저장

🚫 WordPress 발행 없음 — 로컬 검증 전용
"""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from pathlib import Path
from datetime import datetime

from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository
from modules.calculator_seo_generator import generate_seo
from modules.calculator_faq_generator import generate_faq
from modules.calculator_pipeline import write_article_for_rewrite, _load_prompt
from modules.publish_quality import check_gates, _check_g8, _plain_text, _count_dead_links
from modules import cleaner

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "workspace" / "phase5_2b"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 5개 대표 샘플 (S1~S5)
SAMPLES = [
    {"id": "S1", "slug": "weekly-holiday-allowance",  "focus": "Gate A-1/A-2"},
    {"id": "S2", "slug": "severance-pay",             "focus": "Gate B (자발적퇴사 법률오류)"},
    {"id": "S3", "slug": "unemployment-benefit",      "focus": "Gate A-1/A-2"},
    {"id": "S4", "slug": "연말정산_환급액_계산기",      "focus": "Gate A-4 (placeholder) + SEO"},
    {"id": "S5", "slug": "육아휴직_급여_계산기",        "focus": "Gate A-1/A-2"},
]

# Gate B: 퇴직금 오류 패턴 (forbidden_phrases와 독립적으로 raw 탐색용)
_SEVERANCE_ERROR_PATTERNS = [
    "자발적 퇴사의 경우 퇴직금 수령이 어려울",
    "자발적으로 퇴사하는 경우 퇴직금 수령이 어려울",
    "자발적 퇴사이면 퇴직금을 받기 어렵",
    "자진퇴사의 경우 퇴직금을 받기 어렵",
    "자발적 퇴사.*?퇴직금.*?(?:어렵|불가|수령.*?어렵)",
]

def find_error_sentences(text: str) -> list:
    """퇴직금 자발적퇴사 오류 문장 탐색. literal + regex 결합."""
    found = []
    for pat in _SEVERANCE_ERROR_PATTERNS:
        try:
            if re.search(pat, text):
                # 해당 문장 추출 (최대 100자)
                m = re.search(pat, text)
                if m:
                    start = max(0, m.start() - 10)
                    end = min(len(text), m.end() + 40)
                    found.append(text[start:end].strip())
        except re.error:
            if pat in text:
                found.append(pat)
    return found


def _default_keyword(calc: dict) -> str:
    return calc.get("name", "") + " 계산 방법"


def run_sample(cfg: dict, calc: dict, sample_meta: dict) -> dict:
    sid = sample_meta["id"]
    slug = sample_meta["slug"]
    print(f"\n{'='*60}")
    print(f"[{sid}] {calc['name']} ({slug})")
    print(f"  집중 검증: {sample_meta['focus']}")
    print(f"{'='*60}")

    result = {
        "sample_id": sid,
        "slug": slug,
        "name": calc["name"],
        "focus": sample_meta["focus"],
        "timestamp": datetime.now().isoformat(),
    }

    # 1) SEO
    print("  SEO 생성 중...")
    try:
        seo = generate_seo(cfg, calc)
        result["seo"] = seo
        print(f"  SEO: {seo.get('seo_title','')[:50]}")
    except Exception as e:
        print(f"  SEO 실패: {e}")
        seo = {"seo_title": f"{calc['name']} 계산 방법", "seo_description": ""}

    # 2) FAQ
    print("  FAQ 생성 중...")
    try:
        faq = generate_faq(cfg, calc)
        result["faq_count"] = len(faq) if isinstance(faq, list) else 0
        print(f"  FAQ: {result['faq_count']}개")
    except Exception as e:
        print(f"  FAQ 실패: {e}")
        faq = []

    # 3) 본문 생성 (write_article_for_rewrite = _write_article의 공개 wrapper)
    keyword = _default_keyword(calc)
    print(f"  본문 생성 중 (keyword={keyword!r})...")
    try:
        body_raw, tokens = write_article_for_rewrite(cfg, calc, keyword, seo, faq)
        result["body_tokens"] = tokens
        print(f"  본문 생성 완료: {len(body_raw)}chars, {tokens}tokens")
    except Exception as e:
        print(f"  본문 생성 실패: {e}")
        result["error"] = str(e)
        return result

    # body_raw는 이미 strip_prompt_artifacts가 적용된 상태 (pipeline에서 호출됨)
    body_final = body_raw

    # raw 텍스트 (가시 텍스트)
    raw_text = _plain_text(body_final)

    # 저장
    (OUT_DIR / f"{sid}_{slug}_body.html").write_text(body_final, encoding="utf-8")

    # 4) Gate 검사
    print("  Gate 검사 중...")
    passed, failed_gates = check_gates(body_final, body_final, cfg, link_pool_size=0)
    g8_fails = _check_g8(body_final, calc)

    all_failed = failed_gates + g8_fails
    result["gates_passed"] = passed and len(g8_fails) == 0
    result["failed_gates"] = all_failed

    # Gate 결과 출력
    if not all_failed:
        print("  Gates: ALL PASS")
    else:
        for f in all_failed:
            print(f"  [{f['gate']} / {f['grade']}] {f['detail'][:80]}")

    # 5) S2 퇴직금 전용 3단계 검증
    if slug == "severance-pay":
        print("\n  [S2 Gate B 3단계 검증]")

        # 3-1: raw 결과에 오류 문장 있는지
        error_sentences = find_error_sentences(raw_text)
        result["s2_3_1_error_found"] = len(error_sentences) > 0
        result["s2_3_1_error_sentences"] = error_sentences

        if error_sentences:
            print(f"  3-1: 오류 문장 발견 ({len(error_sentences)}건) → G8으로 차단되어야 함")
            for s in error_sentences:
                print(f"       └ {s[:80]}")
        else:
            print("  3-1: 오류 문장 미발견 (writer_note 예방 성공)")
            print("       → forbidden_phrases 매칭 로직은 합성 테스트로 별도 검증 진행")

        # 3-2: G8이 정확히 잡아냈는지
        g8_matched = [f for f in g8_fails if "자발적" in f.get("detail", "") or "forbidden" in f.get("detail", "").lower()]
        result["s2_3_2_g8_caught"] = len(g8_matched) > 0
        result["s2_3_2_g8_details"] = [f["detail"] for f in g8_matched]

        if g8_matched:
            print(f"  3-2: G8 정확 검출 ({len(g8_matched)}건)")
        else:
            if error_sentences:
                print("  3-2: G8 미검출 (오류는 있으나 패턴 매칭 실패 — 패턴 보완 필요)")
            else:
                print("  3-2: G8 검출 없음 (오류 문장 자체가 없어 검출 대상 없음 — 정상)")

        # 3-3: 최종 HTML에 오류 문장 없는지
        # REWRITE 판정이면 발행 대상 HTML ≠ 이 body → 오류 미노출
        has_critical = any(f.get("grade") == "critical" for f in all_failed)
        result["s2_3_3_final_safe"] = (not error_sentences) or has_critical
        if not error_sentences:
            print("  3-3: PASS — 오류 문장 없음 (사용자에게 오류 노출 없음)")
        elif has_critical:
            print("  3-3: PASS — 오류 문장 있으나 REWRITE 판정으로 발행 차단됨")
        else:
            print("  3-3: ⚠️ FAIL — 오류 문장이 있고 Gate가 차단하지 못함 (수동 검토 필요)")

        # forbidden_phrases 합성 테스트 (3-1에서 오류가 없었을 때)
        if not error_sentences:
            print("\n  [합성 테스트] forbidden_phrases 매칭 독립 검증")
            synth_html = (
                "<p>퇴직금은 근로자퇴직급여 보장법 제8조에 따라 지급됩니다. 고용노동부 기준.</p>"
                "<p>자발적 퇴사의 경우 퇴직금 수령이 어려울 수 있습니다.</p>"
                "<p>계속근로기간 1년 이상이면 지급 대상입니다.</p>"
            )
            synth_fails = _check_g8(synth_html, calc)
            synth_forbidden = [f for f in synth_fails if "자발적" in f.get("detail", "")]
            result["s2_synth_test_passed"] = len(synth_forbidden) > 0
            if synth_forbidden:
                print(f"  합성 테스트 PASS — G8이 forbidden_phrases 정확 검출: {synth_forbidden[0]['detail'][:60]}")
            else:
                print("  합성 테스트 FAIL — forbidden_phrases 패턴 매칭 로직 문제 있음 (즉시 수정 필요)")

    # 6) 항목별 PASS/FAIL 집계
    gate_ids = [f["gate"] for f in all_failed]
    result["check_summary"] = {
        "A1_prompt_artifact":     "FAIL" if "A1" in gate_ids else "PASS",
        "A2_dead_link":           "FAIL" if ("A2" in gate_ids or "G5" in gate_ids) else "PASS",
        "A3_hallucinated_calc":   "FAIL" if "A3" in gate_ids else "PASS",
        "A4_placeholder":         "FAIL" if "A4" in gate_ids else "PASS",
        "G8_legal_basis":         "FAIL" if "G8" in gate_ids else "PASS",
        "G1_length":              "FAIL" if "G1" in gate_ids else "PASS",
        "G3_faq":                 "FAIL" if "G3" in gate_ids else "PASS",
    }
    return result


def run_all():
    print("Phase 5-2-B 대표 샘플 재생성 검증")
    print(f"출력: {OUT_DIR}")
    print(f"시작: {datetime.now().isoformat()}")

    cfg = load_config()
    repo = CalculatorRepository(get_db_adapter(cfg))
    calcs = {c["slug"]: c for c in repo.get_all()}

    all_results = []
    for meta in SAMPLES:
        slug = meta["slug"]
        calc = calcs.get(slug)
        if not calc:
            print(f"\n[{meta['id']}] {slug} — DB에서 찾을 수 없음, 건너뜀")
            continue
        r = run_sample(cfg, calc, meta)
        all_results.append(r)
        # 샘플별 JSON 저장
        (OUT_DIR / f"{meta['id']}_{slug}_result.json").write_text(
            json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # Before/After 비교표 출력
    print("\n" + "="*70)
    print("BEFORE/AFTER 비교표 (Phase 5-1 기준 → 재생성 결과)")
    print("="*70)
    before_known = {
        "weekly-holiday-allowance": {"A1": "FAIL(번호H2+CTA헤딩)", "A2": "FAIL(href=#)"},
        "severance-pay":             {"G8_자발적퇴사": "FAIL(Phase5-1 발견)"},
        "unemployment-benefit":      {"A1": "FAIL(번호H2)", "A2": "FAIL(href=#)"},
        "연말정산_환급액_계산기":      {"A4": "미확인"},
        "육아휴직_급여_계산기":        {"A1": "미확인", "A2": "미확인"},
    }

    print(f"\n{'샘플':<4} {'항목':<22} {'Before(5-1)':<25} {'After(재생성)':<12} 판정")
    print("-"*75)
    for r in all_results:
        slug = r["slug"]
        sid  = r["sample_id"]
        summ = r.get("check_summary", {})
        items_map = {
            "A1_prompt_artifact":   "H2/CTA artifact",
            "A2_dead_link":         "dead link(href=#)",
            "A3_hallucinated_calc": "환각 계산기 링크",
            "A4_placeholder":       "placeholder 누출",
            "G8_legal_basis":       "법적 근거(G8)",
            "G1_length":            "본문 길이(G1)",
            "G3_faq":               "FAQ 개수(G3)",
        }
        for key, label in items_map.items():
            after = summ.get(key, "N/A")
            before_info = "-"
            if slug in before_known:
                # 대략적 before 정보
                for bk, bv in before_known[slug].items():
                    if any(k in key for k in bk.split("_")):
                        before_info = bv
                        break
            verdict = "✅ PASS" if after == "PASS" else "❌ FAIL"
            print(f"{sid:<4} {label:<22} {before_info:<25} {after:<12} {verdict}")
        # S2 Gate B 특이사항
        if slug == "severance-pay":
            s2_safe = r.get("s2_3_3_final_safe", False)
            synth = r.get("s2_synth_test_passed")
            print(f"{sid:<4} {'자발적퇴사 raw':<22} {'FAIL(5-1발견)':<25} {'안나옴' if not r.get('s2_3_1_error_found') else '나옴':<12} {'✅' if not r.get('s2_3_1_error_found') else '→G8차단'}")
            print(f"{sid:<4} {'forbidden합성테스트':<22} {'-':<25} {'PASS' if synth else 'FAIL':<12} {'✅ PASS' if synth else '❌ 수정필요'}")
            print(f"{sid:<4} {'최종HTML 오류없음':<22} {'-':<25} {'PASS' if s2_safe else 'FAIL':<12} {'✅ PASS' if s2_safe else '❌ FAIL'}")

    # 전체 결과 JSON 저장
    summary_path = OUT_DIR / "phase5_2b_summary.json"
    summary_path.write_text(
        json.dumps({"timestamp": datetime.now().isoformat(), "results": all_results},
                   ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"\n결과 저장: {summary_path}")

    # DoD 체크리스트
    print("\n" + "="*70)
    print("DoD 체크리스트")
    print("="*70)
    any_fail = any(
        v == "FAIL"
        for r in all_results
        for v in r.get("check_summary", {}).values()
    )
    s2_r = next((r for r in all_results if r["slug"] == "severance-pay"), {})
    items_dod = [
        ("S1~S5 재생성 완료",          len(all_results) == 5),
        ("S2 3단계 검증 수행",          "s2_3_3_final_safe" in s2_r),
        ("dead link 0건",              all(r.get("check_summary",{}).get("A2_dead_link") == "PASS" for r in all_results)),
        ("환각 계산기 0건",             all(r.get("check_summary",{}).get("A3_hallucinated_calc") == "PASS" for r in all_results)),
        ("prompt artifact 0건",        all(r.get("check_summary",{}).get("A1_prompt_artifact") == "PASS" for r in all_results)),
        ("placeholder 0건",            all(r.get("check_summary",{}).get("A4_placeholder") == "PASS" for r in all_results)),
        ("S2 최종HTML 오류없음",        s2_r.get("s2_3_3_final_safe", False)),
        ("forbidden_phrases 합성검증", s2_r.get("s2_synth_test_passed", False)),
        ("전체 FAIL 없음",             not any_fail),
    ]
    for label, ok in items_dod:
        print(f"  [{'✅' if ok else '❌'}] {label}")

    next_phase = "Phase 5-3 (37개 전체 재처리 판단)" if not any_fail else "발견된 FAIL 항목 최소 수정 후 재검증"
    print(f"\n→ 다음 단계: {next_phase}")
    print(f"\n완료: {datetime.now().isoformat()}")


if __name__ == "__main__":
    run_all()
