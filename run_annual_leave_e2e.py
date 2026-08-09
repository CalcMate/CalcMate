# -*- coding: utf-8 -*-
"""
run_annual_leave_e2e.py — 연차잔여일계산기 Contract 기반 재생성 + 저장 전 E2E 검증

실행: python run_annual_leave_e2e.py
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from modules.app_factory import (
    build_contract, validate_against_contract, generate_app,
    save_app, get_af_checklist,
)
from modules.formula_engine import (
    detect_schema_drift, validate_formula, validate_formula_with_samples,
)
from modules.review_center import check_slug_conflict, extract_checklist

# ── 확정 Contract ──────────────────────────────────────────────────────────
TARGET_SLUG = "annual-leave-remaining"
TARGET_NAME = "연차 잔여일 계산기"

CONTRACT_FORMULA = {
    "total_days": "15 + min(max(0, (years_of_service - 1) // 2), 10)",
    "remaining_days": "15 + min(max(0, (years_of_service - 1) // 2), 10) - used_days",
}

CONTRACT_TEST_CASES = [
    # (근속연수, 사용일수) → (total, remaining)
    {"input": {"years_of_service": 1,  "used_days": 0}, "expected": {"total_days": 15.0, "remaining_days": 15.0}},
    {"input": {"years_of_service": 3,  "used_days": 5}, "expected": {"total_days": 16.0, "remaining_days": 11.0}},
    {"input": {"years_of_service": 21, "used_days": 0}, "expected": {"total_days": 25.0, "remaining_days": 25.0}},
    {"input": {"years_of_service": 30, "used_days": 0}, "expected": {"total_days": 25.0, "remaining_days": 25.0}},
]

CONTRACT_INPUT_SCHEMA = {"years_of_service": "number", "used_days": "number"}


def sep(title=""):
    line = "=" * 60
    print(f"\n{line}")
    if title:
        print(f"  {title}")
        print(line)


def main():
    cfg = load_config()

    # ────────────────────────────────────────────────────────────────────────
    # STEP 1: 기존 Contract 위반 생성물 확인
    # ────────────────────────────────────────────────────────────────────────
    sep("STEP 1: 기존 Contract 위반 생성물 폐기/미존재 확인")

    from adapters.db.factory import get_db_adapter
    from repositories.calculator_repository import CalculatorRepository

    try:
        calcs = CalculatorRepository(get_db_adapter(cfg)).get_all()
        slugs_in_db = [c.get("slug", "") for c in calcs]
        names_in_db = [c.get("name", "") for c in calcs]

        suspect_slugs = [s for s in slugs_in_db
                         if s in ("annual-leave", "annual-leave-remaining", "연차사용계획")]
        suspect_names = [n for n in names_in_db
                         if "연차" in str(n) and "연차수당" not in str(n) and "연차잔여" not in str(n)
                         and "연차 잔여" not in str(n)]

        if suspect_slugs:
            print(f"⚠️ 경고: DB에 이전 생성물 발견 — slug={suspect_slugs}")
            print("   저장 전 운영자가 직접 확인/삭제 필요 (이 스크립트는 삭제하지 않음)")
            return
        else:
            print(f"✅ DB 전체 계산기 수: {len(calcs)}")
            print(f"   annual-leave / annual-leave-remaining / 연차사용계획 미저장 확인")
            if suspect_names:
                print(f"   참고: 유사 이름 계산기 발견(확인 필요): {suspect_names}")
    except Exception as e:
        print(f"⚠️ DB 조회 실패(진행 계속): {e}")

    # Registry _af.yaml 확인
    from modules.registry_loader import load_registry_v3
    v3 = load_registry_v3(force=True)
    if TARGET_SLUG in v3:
        status = v3[TARGET_SLUG].get("status", "?")
        print(f"⚠️ Registry v3에 이미 {TARGET_SLUG!r} 존재 (status={status}) — 중복 저장 차단됨")
        print("   이미 정상 저장된 경우 STEP 5~6으로 이동. 그렇지 않으면 수동 확인 필요.")
        # 이미 저장된 경우 검토 항목 확인만 진행
        _show_review_items(cfg, TARGET_SLUG, {})
        return
    else:
        print(f"✅ Registry v3에 {TARGET_SLUG!r} 미존재 — 신규 저장 가능")

    # Slug 충돌 사전 검사
    _, slug_conflict, slug_msg = check_slug_conflict(TARGET_SLUG, cfg)
    if slug_conflict:
        print(f"⚠️ Slug 충돌: {slug_msg}")
        return
    print(f"✅ Slug 중복 없음: {TARGET_SLUG!r}")

    # ────────────────────────────────────────────────────────────────────────
    # STEP 2: App Factory 재생성
    # ────────────────────────────────────────────────────────────────────────
    sep("STEP 2: App Factory 재생성 (AI 호출)")

    # desc에 확정 필드명/공식을 명시하여 AI가 틀린 필드명을 생성하지 않도록 유도
    desc = (
        "입력: years_of_service(근속연수, 양의 정수), used_days(이미 사용한 연차일수, 0 이상 정수). "
        "출력: total_days(올해 총 연차일수), remaining_days(잔여 연차일수). "
        "공식(dict): "
        "total_days = 15 + min(max(0, (years_of_service - 1) // 2), 10), "
        "remaining_days = 15 + min(max(0, (years_of_service - 1) // 2), 10) - used_days. "
        "법적근거: 근로기준법 제60조 제1항(15일), 제4항(2년마다 1일 가산, 최대 25일). "
        "전제조건(화면 표시): 근속 1년 이상, 출근율 80% 이상, 통상 근로자(단시간 제외), 입사일 기준."
    )

    print(f"계산기명: {TARGET_NAME}")
    print(f"카테고리: 노동/고용법 / Tier: 2(Tier2-A)")
    print(f"desc 길이: {len(desc)}자")
    print("AI 생성 중 (GPT spec → Claude HTML → GPT SEO → Gemini 이미지)...")

    try:
        app = generate_app(cfg, TARGET_NAME, category="노동/고용법", desc=desc, tier=2)
    except Exception as e:
        print(f"❌ generate_app 실패: {e}")
        return

    print(f"\n생성 완료 — 총 토큰: {app.get('_tokens', 0):,}")
    ai_formula = app.get("formula", "")
    print(f"AI input_schema  키: {list(app.get('input_schema', {}).keys())}")
    print(f"AI output_schema 키: {list(app.get('output_schema', {}).keys())}")
    if isinstance(ai_formula, dict):
        print(f"AI formula(dict): {json.dumps(ai_formula, ensure_ascii=False)}")
    else:
        print(f"AI formula(str): {str(ai_formula)[:200]}")
    print(f"AI formula 구문 사전검증: _formula_valid={app.get('_formula_valid')}, msg={app.get('_formula_msg')}")

    # ────────────────────────────────────────────────────────────────────────
    # STEP 3: 4가지 자동검증
    # ────────────────────────────────────────────────────────────────────────
    sep("STEP 3: 4가지 자동검증")

    contract = build_contract(
        slug=TARGET_SLUG, name=TARGET_NAME, category="노동/고용법", tier="Tier2-A",
        input_fields=["years_of_service", "used_days"],
        output_fields=["total_days", "remaining_days"],
        formula=CONTRACT_FORMULA,
        scope_exclusions=["1년 미만 근무자", "단시간 근로자", "회계연도 기준"],
        test_cases=CONTRACT_TEST_CASES,
    )

    # V1: Schema 일치
    drift = detect_schema_drift(contract, app)
    v1_pass = not drift["drifted"]
    print(f"\n[V1] Schema 일치 (Contract vs AI 생성 필드명): {'✅ PASS' if v1_pass else '❌ FAIL'}")
    if v1_pass:
        print(f"     입력  : {contract['input_fields']} ✅")
        print(f"     출력  : {contract['output_fields']} ✅")
    else:
        print(f"     Contract 입력: {contract['input_fields']}")
        print(f"     AI 생성 입력: {list(app.get('input_schema', {}).keys())}")
        print(f"     Contract 출력: {contract['output_fields']}")
        print(f"     AI 생성 출력: {list(app.get('output_schema', {}).keys())}")
        for c in drift["changes"]:
            t = c.get("type", "")
            if "missing" in t:
                print(f"     ❌ 누락: Contract의 {c.get('contract')!r}가 AI 결과에 없음")
            else:
                print(f"     ❌ 추가: AI의 {c.get('ai')!r} (Contract에 없음)")

    # V2: Slug 일치
    # generate_app은 slug 반환 안 함 — 저장 시 운영자(스크립트)가 TARGET_SLUG를 명시적으로 전달
    v2_pass = True
    print(f"\n[V2] Slug 일치 (운영자 확정): {'✅ PASS' if v2_pass else '❌ FAIL'}")
    print(f"     저장 예정 slug: {TARGET_SLUG!r} (Contract 확정값 직접 사용)")
    print(f"     Registry/DB 사전 중복검사: ✅ 이미 확인 완료 (STEP 1)")

    # V3: Formula 일치 (구문 + cap 구조)
    ai_formula = app.get("formula", "")
    ai_schema = app.get("input_schema", {})
    v3_syntax_ok, v3_msg = validate_formula(ai_formula, ai_schema)
    # cap 구조: min()/max() 포함 여부
    formula_str_for_cap = (json.dumps(ai_formula, ensure_ascii=False)
                           if isinstance(ai_formula, dict) else str(ai_formula))
    v3_cap_ok = bool(re.search(r'\bmin\s*\(', formula_str_for_cap) and
                     re.search(r'\bmax\s*\(', formula_str_for_cap))
    v3_pass = v3_syntax_ok and v3_cap_ok

    # formula 텍스트 비교 (참고용)
    c_validation = validate_against_contract(contract, app)
    formula_text_changed = c_validation["formula_changed"]

    print(f"\n[V3] Formula 일치 (구문+cap 구조): {'✅ PASS' if v3_pass else '❌ FAIL'}")
    print(f"     구문 검증: {'✅ OK' if v3_syntax_ok else f'❌ {v3_msg}'}")
    print(f"     cap 구조(min/max): {'✅ 있음' if v3_cap_ok else '❌ 없음 — 25일 상한 미적용 위험'}")
    if formula_text_changed:
        print(f"     참고: AI formula 텍스트가 Contract와 상이 (수학적 동일성은 V4에서 확인)")
    else:
        print(f"     참고: AI formula 텍스트가 Contract와 일치")

    # V4: 샘플 계산 결과 일치
    # Contract input schema(확정 필드명)로 Contract test cases를 실행
    # → AI formula가 Contract 필드명을 사용하지 않으면 이 단계에서 실패
    sample_res = validate_formula_with_samples(ai_formula, CONTRACT_INPUT_SCHEMA, CONTRACT_TEST_CASES)

    if sample_res["valid"]:
        v4_pass = all(sr.get("match") is True for sr in sample_res["sample_results"])
    else:
        v4_pass = False

    print(f"\n[V4] 샘플 계산 결과 일치 (Contract test cases): {'✅ PASS' if v4_pass else '❌ FAIL'}")
    if not sample_res["valid"]:
        print(f"     formula 실행 오류: {sample_res['message']}")
        if "미정의 변수" in sample_res["message"] and not v1_pass:
            print("     → V1 Schema 불일치(필드명 변경)로 인해 Contract 테스트 케이스 실행 불가")
    else:
        for sr in sample_res["sample_results"]:
            inp = sr["input"]
            out = sr.get("output") or {}
            exp = sr.get("expected") or {}
            match = sr.get("match")
            err = sr.get("error", "")
            status = "✅" if match else ("⚠️ ERROR" if err else "❌")
            td = out.get("total_days", "N/A")
            rd = out.get("remaining_days", "N/A")
            etd = exp.get("total_days")
            erd = exp.get("remaining_days")
            print(f"     {status} 근속{inp.get('years_of_service')}년/사용{inp.get('used_days')}일 "
                  f"→ total={td}(기대:{etd}), remaining={rd}(기대:{erd})"
                  + (f" | 오류: {err}" if err else ""))

    # ────────────────────────────────────────────────────────────────────────
    # 검증 합계
    # ────────────────────────────────────────────────────────────────────────
    sep("검증 결과 요약")
    results = {
        "V1 Schema 일치": v1_pass,
        "V2 Slug 일치":   v2_pass,
        "V3 Formula 구문+cap": v3_pass,
        "V4 샘플 계산 일치": v4_pass,
    }
    for label, passed in results.items():
        print(f"  {'✅' if passed else '❌'} {label}: {'PASS' if passed else 'FAIL'}")

    all_pass = all(results.values())
    print(f"\n저장 가능 여부: {'✅ 전부 통과 — 저장 진행' if all_pass else '❌ 불일치 발견 — 저장 중단'}")

    if not all_pass:
        print("\n⛔ 검증 실패 — 저장하지 않습니다.")
        _print_failure_analysis(v1_pass, v3_pass, v4_pass, contract, app, sample_res)
        return

    # ────────────────────────────────────────────────────────────────────────
    # STEP 4-5: 저장 + HOLD 확인
    # ────────────────────────────────────────────────────────────────────────
    sep("STEP 4: 저장 진행 (calculators + app_templates + Registry v3)")

    # app에 legal_refs 및 _schema_drift embed (review_center용)
    app["legal_refs"] = ["근로기준법 제60조 제1항", "근로기준법 제60조 제4항"]
    app["_schema_drift"] = drift  # drifted=False (V1 통과했으므로)

    save_ok, save_msg = save_app(cfg, app, slug=TARGET_SLUG)
    print(f"저장 결과: {'✅' if save_ok else '❌'} {save_msg}")

    if not save_ok:
        print("\n❌ 저장 실패 — 위 메시지 확인 필요")
        return

    sep("STEP 5: HOLD 상태 확인")

    from modules.registry_loader import load_registry_v3
    v3_registry = load_registry_v3(force=True)
    entry = v3_registry.get(TARGET_SLUG, {})
    reg_status = entry.get("status", "미존재")
    print(f"Registry v3 [{TARGET_SLUG}] status: {reg_status}")
    if reg_status == "HOLD":
        print("✅ HOLD 상태 확인 완료 — legal 검증 + READY 전환 대기 상태")
    else:
        print(f"⚠️ 예상 HOLD와 상이: {reg_status}")

    sep("STEP 6: Review Center 6개 항목 확인")
    _show_review_items(cfg, TARGET_SLUG, app)

    print("\n" + "=" * 60)
    print("E2E 완료")
    print("다음: 운영자가 대시보드 Review Center에서 🔴 항목을 직접 검토·체크 후")
    print("      READY 전환 → Build QA → Build → 수동 배포 진행")
    print("=" * 60)


def _print_failure_analysis(v1_pass, v3_pass, v4_pass, contract, app, sample_res):
    """검증 실패 시 원인 분석 출력."""
    print("\n[원인 분석]")
    if not v1_pass:
        print("■ V1 Schema 불일치:")
        print(f"  Contract 확정 입력 필드: {contract['input_fields']}")
        print(f"  AI 생성 입력 필드    : {list(app.get('input_schema', {}).keys())}")
        print(f"  Contract 확정 출력 필드: {contract['output_fields']}")
        print(f"  AI 생성 출력 필드    : {list(app.get('output_schema', {}).keys())}")
        print("  → AI 오케스트레이터가 확정 필드명을 임의 변경했습니다.")
        print("  → 이 Contract 검증 시스템이 정확히 감지했습니다 ✅")
        print("  → 개선 방안: desc에 필드명을 더 명시적으로 포함시켜 AI 재실행 필요")

    if not v3_pass:
        ai_formula = app.get("formula", "")
        formula_str = (json.dumps(ai_formula, ensure_ascii=False)
                       if isinstance(ai_formula, dict) else str(ai_formula))
        print("\n■ V3 Formula 구조 불일치:")
        print(f"  AI formula: {formula_str[:300]}")
        print(f"  Contract formula: {json.dumps(contract['formula'], ensure_ascii=False)}")
        if not re.search(r'\bmin\s*\(', formula_str) or not re.search(r'\bmax\s*\(', formula_str):
            print("  → min()/max() cap 구조 미포함 — 25일 상한 미적용 위험")

    if not v4_pass and sample_res.get("valid") is False:
        print("\n■ V4 샘플 계산 실패:")
        print(f"  오류: {sample_res.get('message', '')}")
        if "미정의 변수" in str(sample_res.get("message", "")):
            print("  → AI formula가 Contract 필드명을 사용하지 않아 테스트 케이스 실행 불가")


def _show_review_items(cfg, slug, app):
    """저장된 체크리스트 또는 app dict에서 Review Center 항목 표시."""
    # 저장 후 _af.yaml에서 체크리스트 로드
    try:
        checklist = get_af_checklist(slug)
    except Exception:
        checklist = []

    if checklist:
        print(f"저장된 체크리스트 항목 수: {len(checklist)}")
        for item in checklist:
            emoji = "🔴" if item.get("severity") == "critical" else "🟡"
            print(f"  {emoji} [{item['id']}] {item['label']}")
            disp = str(item.get("display_value", ""))
            print(f"     → {disp[:80]}{'...' if len(disp) > 80 else ''}")
            print(f"     checked={item['checked']}")
    elif app:
        # app dict로 직접 추출 (저장 전 시뮬레이션)
        sim_app = dict(app)
        if "_schema_drift" not in sim_app:
            sim_app["_schema_drift"] = {"drifted": False, "changes": [],
                                         "input_changes": [], "output_changes": []}
        items = extract_checklist(sim_app, tier="Tier2-A", category="노동/고용법")
        print(f"(저장 후 _af.yaml 항목 없음 — app dict 기준 시뮬레이션, {len(items)}개)")
        for item in items:
            emoji = "🔴" if item.get("severity") == "critical" else "🟡"
            print(f"  {emoji} [{item['id']}] {item['label']}")
    else:
        print("체크리스트 정보를 가져올 수 없습니다.")


if __name__ == "__main__":
    main()
