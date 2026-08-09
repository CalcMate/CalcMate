# -*- coding: utf-8 -*-
"""
run_phase2_repro_test.py — 프롬프트 강화 후 재현성 검증 (3회 반복)

Contract: 연차 잔여일 계산기 테스트 / annual-leave-remaining-test
저장 없음 — 검증 후 폐기.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from modules.app_factory import build_contract, generate_app_with_contract, AF_SESSION_DISCARD_KEYS
from modules.formula_engine import validate_formula_with_samples

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

RUNS = 3


def run_once(cfg, run_no: int) -> dict:
    print(f"\n{'='*65}")
    print(f"  RUN {run_no}/{RUNS}")
    print(f"{'='*65}")

    contract = build_contract(
        slug="annual-leave-remaining-test",
        name="연차 잔여일 계산기 테스트",
        category="노동/고용법",
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
        print(f"  ❌ 생성 실패: {e}")
        return {"run": run_no, "ok": False, "error": str(e)}

    cv = app.get("_contract_validation", {})
    drift = app.get("_schema_drift", {})
    ai_in = list(app.get("input_schema", {}).keys())
    ai_out = list(app.get("output_schema", {}).keys())
    ai_formula = app.get("formula", "")

    schema_ok = not drift.get("drifted", True)
    slug_ok = not cv.get("slug_mismatch", False)
    formula_ok = not cv.get("formula_changed", False)

    formula_str = (json.dumps(ai_formula, ensure_ascii=False)
                   if isinstance(ai_formula, dict) else str(ai_formula))
    cap_ok = bool(re.search(r'\bmin\s*\(', formula_str) and re.search(r'\bmax\s*\(', formula_str))

    tc_res = validate_formula_with_samples(ai_formula, app.get("input_schema", {}), CONTRACT_TEST_CASES)
    tc_ok = tc_res.get("valid", False) and all(s.get("match") is True for s in tc_res.get("sample_results", []))

    overall = cv.get("valid", False) and cap_ok and tc_ok

    print(f"  토큰: {app.get('_tokens', 0):,}")
    print(f"  input_schema:  {ai_in}")
    print(f"  output_schema: {ai_out}")
    print(f"  formula:       {formula_str[:100]}...")
    print(f"  Schema  : {'✅ PASS' if schema_ok else '❌ FAIL'}  (drift={drift.get('drifted')})")
    print(f"  Slug    : {'✅ PASS' if slug_ok else '❌ FAIL'}")
    print(f"  Formula : {'✅ PASS' if formula_ok and cap_ok else '❌ FAIL'}  (changed={cv.get('formula_changed')}, cap={cap_ok})")
    print(f"  TestCase: {'✅ PASS' if tc_ok else '❌ FAIL'}")
    if not tc_ok:
        for s in tc_res.get("sample_results", []):
            icon = "✅" if s.get("match") else "❌"
            print(f"    {icon} {s.get('input')} → {s.get('output')} (기대: {s.get('expected')})")
    print(f"  ──> 종합: {'✅ PASS' if overall else '❌ FAIL'}")

    return {
        "run": run_no,
        "ok": overall,
        "schema": schema_ok,
        "slug": slug_ok,
        "formula": formula_ok and cap_ok,
        "testcase": tc_ok,
        "tokens": app.get("_tokens", 0),
    }


def main():
    cfg = load_config()
    print(f"\n{'='*65}")
    print(f"  프롬프트 강화 후 재현성 검증 ({RUNS}회 반복)")
    print(f"  Contract: annual-leave-remaining-test")
    print(f"  저장 없음 — 검증 후 폐기")
    print(f"{'='*65}")

    results = []
    for i in range(1, RUNS + 1):
        r = run_once(cfg, i)
        results.append(r)

    print(f"\n{'='*65}")
    print(f"  최종 결과 요약")
    print(f"{'='*65}")
    pass_count = sum(1 for r in results if r.get("ok"))
    for r in results:
        ok = r.get("ok", False)
        print(f"  Run {r['run']}: {'✅ PASS' if ok else '❌ FAIL'}"
              f"  Schema={'P' if r.get('schema') else 'F'}"
              f"  Formula={'P' if r.get('formula') else 'F'}"
              f"  TestCase={'P' if r.get('testcase') else 'F'}"
              f"  tok={r.get('tokens', 0):,}")
    print(f"\n  성공률: {pass_count}/{RUNS}")
    print(f"  저장: 수행하지 않음")


if __name__ == "__main__":
    main()
