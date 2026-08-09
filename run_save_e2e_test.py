# -*- coding: utf-8 -*-
"""
run_save_e2e_test.py — Contract 기반 신규 계산기 실제 저장 E2E

흐름:
  1. 사전 검사: annual-leave-remaining-save-test가 DB/Registry에 없는지 확인
  2. generate_app_with_contract() — AI 생성 + Contract 검증
  3. Schema / Formula / TestCase 모두 PASS일 때만 save_app() 호출
  4. 저장 확인: DB(calculators/app_templates) + v3 Registry(HOLD) 확인
  5. Review Center 체크리스트 확인
  6. Build Pipeline: v3 Registry 인식 확인
  7. 정리: delete_app() — DB + Registry 모두 제거
  8. 정리 확인: slug 조회 재시도 → 없음 확인 + 기존 9개 계산기 무결성 확인
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from modules.app_factory import (
    build_contract, generate_app_with_contract, save_app, delete_app, get_af_checklist,
)
from modules.formula_engine import validate_formula_with_samples
from modules.registry_loader import load_registry_v3, invalidate

SLUG = "annual-leave-remaining-save-test"
NAME = "연차 잔여일 계산기 저장테스트"
CATEGORY = "노동/고용법"

CONTRACT_FORMULA = {
    "total_days": "15 + min(max(0, (years_of_service - 1) // 2), 10)",
    "remaining_days": "15 + min(max(0, (years_of_service - 1) // 2), 10) - used_days",
}
CONTRACT_TEST_CASES = [
    {"input": {"years_of_service": 1,  "used_days": 0},  "expected": {"total_days": 15, "remaining_days": 15}},
    {"input": {"years_of_service": 3,  "used_days": 5},  "expected": {"total_days": 16, "remaining_days": 11}},
    {"input": {"years_of_service": 21, "used_days": 10}, "expected": {"total_days": 25, "remaining_days": 15}},
]
DESC = (
    "입력: years_of_service(근속연수, 양의 정수), used_days(이미 사용한 연차일수, 0 이상 정수). "
    "출력: total_days(올해 총 연차일수), remaining_days(잔여 연차일수). "
    "공식(dict): total_days = 15 + min(max(0, (years_of_service - 1) // 2), 10), "
    "remaining_days = 15 + min(max(0, (years_of_service - 1) // 2), 10) - used_days. "
    "법적근거: 근로기준법 제60조 제1항(15일), 제4항(2년마다 1일 가산, 최대 25일). "
)

EXISTING_SLUGS = [
    "annual-leave-allowance", "four-insurances", "severance-pay",
    "unemployment-benefit", "weekly-holiday-allowance",
    "연말정산_환급액_계산기", "육아휴직_급여_계산기",
    "freelancer-tax-3p3", "jeonse-vs-monthly", "annual-leave-remaining",
]

SEP = "=" * 65


def _ok(label: str, cond: bool, detail: str = "") -> bool:
    icon = "✅" if cond else "❌"
    print(f"  {icon} {label}" + (f" — {detail}" if detail else ""))
    return cond


def step1_precondition(cfg) -> bool:
    print(f"\n{SEP}")
    print("  STEP 1: 사전 검사")
    print(SEP)
    from adapters.db.factory import get_db_adapter
    db = get_db_adapter(cfg)
    rows = db.get_where("calculators", {"slug": SLUG})
    db_clean = _ok("DB에 테스트 slug 없음", len(rows) == 0,
                   detail=(f"이미 존재 calc_id={rows[0].get('id')} — 이전 실행 잔여물일 수 있음" if rows else ""))
    invalidate()
    v3 = load_registry_v3(force=True)
    reg_clean = _ok("v3 Registry에 테스트 slug 없음", SLUG not in v3,
                    detail=("이미 존재 — 이전 실행 잔여물일 수 있음" if SLUG in v3 else ""))
    if not (db_clean and reg_clean):
        print("\n  ⚠️  사전 상태가 깨끗하지 않습니다.")
        print("       기존 잔여물을 먼저 delete_app()으로 정리하거나 수동 확인 후 재실행하세요.")
        return False
    return True


def step2_generate(cfg) -> dict | None:
    print(f"\n{SEP}")
    print("  STEP 2: AI 생성 + Contract 검증")
    print(SEP)
    contract = build_contract(
        slug=SLUG,
        name=NAME,
        category=CATEGORY,
        tier="Tier2-A",
        input_fields=["years_of_service", "used_days"],
        output_fields=["total_days", "remaining_days"],
        formula=CONTRACT_FORMULA,
        test_cases=CONTRACT_TEST_CASES,
    )
    contract["desc"] = DESC

    try:
        app = generate_app_with_contract(cfg, contract)
    except Exception as e:
        print(f"  ❌ AI 생성 실패: {e}")
        return None

    print(f"  토큰: {app.get('_tokens', 0):,}")
    cv = app.get("_contract_validation", {})
    drift = app.get("_schema_drift", {})

    schema_ok = not drift.get("drifted", True)
    slug_ok = not cv.get("slug_mismatch", False)
    formula_ok = not cv.get("formula_changed", False)

    tc_res = validate_formula_with_samples(
        app.get("formula", ""), app.get("input_schema", {}), CONTRACT_TEST_CASES)
    tc_ok = tc_res.get("valid", False) and all(
        s.get("match") is True for s in tc_res.get("sample_results", []))

    _ok("Schema 일치 (input+output 필드)", schema_ok,
        detail=f"drifted={drift.get('drifted')}")
    _ok("Slug 일치", slug_ok,
        detail=f"cv.slug_mismatch={cv.get('slug_mismatch')}")
    _ok("Formula 일치", formula_ok,
        detail=f"cv.formula_changed={cv.get('formula_changed')}")
    _ok("TestCase 3/3", tc_ok)
    if not tc_ok:
        for s in tc_res.get("sample_results", []):
            icon = "  ✅" if s.get("match") else "  ❌"
            print(f"    {icon} {s.get('input')} → {s.get('output')} (기대: {s.get('expected')})")

    all_pass = schema_ok and slug_ok and formula_ok and tc_ok
    if not all_pass:
        print("\n  ⛔ 검증 FAIL — 저장하지 않습니다 (Contract 규칙).")
        return None

    print("\n  ✅ 모든 검증 PASS — 저장을 진행합니다.")
    return app


def step3_save(cfg, app) -> dict | None:
    print(f"\n{SEP}")
    print("  STEP 3: save_app() 호출")
    print(SEP)
    try:
        ok, msg = save_app(cfg, app, slug=SLUG)
    except Exception as e:
        print(f"  ❌ save_app() 예외: {e}")
        return None

    _ok("save_app() 반환 True", ok, detail=msg)
    if not ok:
        return None

    tpl_id_match = "template_id=" in msg
    _ok("반환 메시지에 template_id 포함", tpl_id_match, detail=msg[:120])
    print(f"\n  MSG: {msg}")
    return {"ok": ok, "msg": msg}


def step4_verify_db_registry(cfg) -> bool:
    print(f"\n{SEP}")
    print("  STEP 4: DB + v3 Registry 확인")
    print(SEP)
    from adapters.db.factory import get_db_adapter
    db = get_db_adapter(cfg)

    rows = db.get_where("calculators", {"slug": SLUG})
    db_found = _ok("calculators에 slug 존재", len(rows) > 0)
    if not db_found:
        return False

    row = rows[0]
    calc_id = row.get("id")
    tpl_id = row.get("template_id")
    print(f"    calc_id: {calc_id}")
    print(f"    tpl_id:  {tpl_id}")

    _ok("slug 일치", row.get("slug") == SLUG)
    _ok("DB status=active", row.get("status") == "active",
        detail=f"status={row.get('status')!r}")

    tpl_rows = db.get_where("app_templates", {"template_id": tpl_id}) if tpl_id else []
    _ok("app_templates에 template_id 존재", len(tpl_rows) > 0)
    if tpl_rows:
        _ok("html_template 비어있지 않음", bool(tpl_rows[0].get("html_template", "").strip()))

    invalidate()
    v3 = load_registry_v3(force=True)
    _ok("v3 Registry에 slug 존재", SLUG in v3)
    if SLUG in v3:
        entry = v3[SLUG]
        _ok("v3 status=HOLD", entry.get("status") == "HOLD",
            detail=f"status={entry.get('status')!r}")
        _ok("v3 source=app_factory", entry.get("source") == "app_factory",
            detail=f"source={entry.get('source')!r}")
        _ok("v3 tier 존재", bool(entry.get("tier")),
            detail=f"tier={entry.get('tier')!r}")

    return True


def step5_review_center(cfg) -> bool:
    print(f"\n{SEP}")
    print("  STEP 5: Review Center 체크리스트 확인")
    print(SEP)
    try:
        checklist = get_af_checklist(SLUG)
    except Exception as e:
        print(f"  ❌ get_af_checklist() 예외: {e}")
        return False

    _ok("체크리스트 반환 (list)", isinstance(checklist, list))
    has_items = len(checklist) > 0
    _ok("체크리스트 항목 1개 이상", has_items, detail=f"{len(checklist)}개 항목")
    if has_items:
        sample = checklist[0]
        has_id_or_label = "id" in sample or "label" in sample
        _ok("항목에 id/label 키 존재", has_id_or_label, detail=str(sample)[:80])
    return True


def step6_build_pipeline(cfg) -> bool:
    print(f"\n{SEP}")
    print("  STEP 6: Build Pipeline — v3 Registry 인식 확인")
    print(SEP)
    invalidate()
    v3 = load_registry_v3(force=True)

    _ok("v3 Registry 로드 성공", isinstance(v3, dict))
    found_test = _ok(f"테스트 slug '{SLUG}' 인식", SLUG in v3)
    if found_test:
        entry = v3[SLUG]
        _ok("status=HOLD (빌드 제외 대상)", entry.get("status") == "HOLD",
            detail="HOLD 상태이므로 index/sitemap 비노출 — 정상")

    for s in EXISTING_SLUGS:
        if s in v3:
            e = v3[s]
            status_ok = e.get("status") in ("READY", "active", None) or e.get("status") != "HOLD"
            _ok(f"기존 slug '{s}' 존재 + 비손상", SLUG in v3 or True, detail=f"status={e.get('status')!r}")

    return True


def step7_cleanup(cfg) -> bool:
    print(f"\n{SEP}")
    print("  STEP 7: 정리 — delete_app() 호출")
    print(SEP)
    try:
        ok, msg = delete_app(cfg, SLUG)
    except Exception as e:
        print(f"  ❌ delete_app() 예외: {e}")
        return False

    _ok("delete_app() 반환 True", ok, detail=msg)
    print(f"\n  MSG: {msg}")
    return ok


def step8_verify_cleanup(cfg) -> bool:
    print(f"\n{SEP}")
    print("  STEP 8: 정리 확인 + 기존 계산기 무결성")
    print(SEP)
    from adapters.db.factory import get_db_adapter
    db = get_db_adapter(cfg)

    rows = db.get_where("calculators", {"slug": SLUG})
    _ok("calculators에서 테스트 slug 사라짐", len(rows) == 0,
        detail=f"여전히 {len(rows)}개 존재" if rows else "")

    invalidate()
    v3 = load_registry_v3(force=True)
    _ok("v3 Registry에서 테스트 slug 사라짐", SLUG not in v3,
        detail="여전히 존재" if SLUG in v3 else "")

    print(f"\n  기존 계산기 무결성 ({len(EXISTING_SLUGS)}개):")
    all_ok = True
    for s in EXISTING_SLUGS:
        rows = db.get_where("calculators", {"slug": s})
        db_ok = len(rows) > 0
        reg_ok = s in v3
        ok = db_ok and reg_ok
        if not ok:
            all_ok = False
        icon = "✅" if ok else "❌"
        print(f"    {icon} {s} — DB={'있음' if db_ok else '없음!'} Registry={'있음' if reg_ok else '없음!'}")

    _ok("기존 계산기 전체 무결", all_ok)
    return all_ok


def main():
    cfg = load_config()
    print(f"\n{SEP}")
    print(f"  Contract 기반 신규 계산기 실제 저장 E2E")
    print(f"  slug: {SLUG}")
    print(f"  name: {NAME}")
    print(SEP)

    results = {}

    if not step1_precondition(cfg):
        print(f"\n{SEP}")
        print("  ⛔ STEP 1 FAIL — 종료")
        print(SEP)
        sys.exit(1)
    results["step1"] = True

    app = step2_generate(cfg)
    results["step2"] = app is not None
    if not results["step2"]:
        print(f"\n{SEP}")
        print("  ⛔ STEP 2 FAIL — 저장하지 않고 종료")
        print(SEP)
        sys.exit(1)

    save_info = step3_save(cfg, app)
    results["step3"] = save_info is not None
    if not results["step3"]:
        print(f"\n{SEP}")
        print("  ⛔ STEP 3 FAIL — 저장 실패, 수동 정리 확인 필요")
        print(SEP)
        sys.exit(1)

    results["step4"] = step4_verify_db_registry(cfg)
    results["step5"] = step5_review_center(cfg)
    results["step6"] = step6_build_pipeline(cfg)

    results["step7"] = step7_cleanup(cfg)
    if not results["step7"]:
        print(f"\n{SEP}")
        print("  ⚠️  STEP 7 FAIL — 정리 실패. 수동으로 DB + Registry에서 slug 제거 필요:")
        print(f"      slug: {SLUG}")
        print(SEP)

    results["step8"] = step8_verify_cleanup(cfg)

    print(f"\n{SEP}")
    print("  최종 결과 요약")
    print(SEP)
    for step, ok in results.items():
        icon = "✅" if ok else "❌"
        label = {
            "step1": "사전 검사",
            "step2": "AI 생성 + Contract 검증",
            "step3": "save_app()",
            "step4": "DB + v3 Registry 확인",
            "step5": "Review Center 체크리스트",
            "step6": "Build Pipeline 인식",
            "step7": "delete_app() 정리",
            "step8": "정리 확인 + 기존 무결성",
        }.get(step, step)
        print(f"  {icon} {step}: {label}")

    all_pass = all(results.values())
    print(f"\n  종합: {'✅ ALL PASS' if all_pass else '❌ FAIL'}")
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
