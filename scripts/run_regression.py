# -*- coding: utf-8 -*-
"""scripts/run_regression.py — 통합 회귀 테스트 러너 + 리포트 생성 (Phase B)

사용법:
  py scripts/run_regression.py                # 전체 실행 + JSON 리포트
  py scripts/run_regression.py --no-report    # 리포트 없이 실행만

출력:
  - 터미널: pytest 결과 스트리밍
  - docs/regression_report.json: 마지막 실행 결과 (suite별 통과/실패/시간)

공유 모듈 영향도:
  4대보험 요율(four-insurances) → 연말정산도 재사용.
  두 suite 모두 포함된 전체 실행에서 영향 범위 전체가 커버됨.
"""
import subprocess
import sys
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT_PATH = ROOT / "docs" / "regression_report.json"

SUITES = [
    ("weekly_holiday",   "tests/test_weekly_holiday_compute.py"),
    ("severance",        "tests/test_severance_compute.py"),
    ("unemployment",     "tests/test_unemployment_benefit_compute.py"),
    ("four_insurances",  "tests/test_four_insurances_compute.py"),
    ("annual_leave",     "tests/test_annual_leave_compute.py"),
    ("parental_leave",   "tests/test_parental_leave_compute.py"),
    ("income_tax",       "tests/test_income_tax_compute.py"),
    ("invariants",       "tests/test_invariants.py"),
]
# snapshot_calculators.py는 직접 실행 스크립트(pytest 미사용) — 별도 처리
SNAPSHOT_SCRIPT = "tests/snapshot_calculators.py"


def run_suite(label: str, path: str) -> dict:
    t0 = time.time()
    result = subprocess.run(
        [sys.executable, "-m", "pytest", path, "--tb=short", "-q"],
        capture_output=True,
        cwd=str(ROOT),
    )
    elapsed = round(time.time() - t0, 2)
    raw = (result.stdout or b"") + (result.stderr or b"")
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    # 마지막 요약 줄 파싱 ("178 passed in 1.47s")
    summary = next((l for l in reversed(lines) if "passed" in l or "failed" in l or "error" in l), "")
    passed = 0; failed = 0
    for part in summary.split():
        if "passed" in part:
            try: passed = int(part.replace("passed",""))
            except: pass
        if "failed" in part:
            try: failed = int(part.replace("failed",""))
            except: pass
    # 숫자가 요약 줄의 앞에 붙는 경우
    import re
    m = re.search(r'(\d+) passed', summary)
    if m: passed = int(m.group(1))
    m = re.search(r'(\d+) failed', summary)
    if m: failed = int(m.group(1))
    return {
        "label": label,
        "path": path,
        "passed": passed,
        "failed": failed,
        "returncode": result.returncode,
        "elapsed_s": elapsed,
        "summary": summary.strip(),
        "stdout_tail": "\n".join(lines[-8:]).encode("ascii", "replace").decode("ascii"),
    }


def main():
    no_report = "--no-report" in sys.argv
    print("=" * 72)
    print("[REGRESSION] calculators x7 + invariants + snapshots")
    print("=" * 72)

    results = []
    total_passed = 0
    total_failed = 0
    all_ok = True
    t_start = time.time()

    for label, path in SUITES:
        print(f"\n▶ {label} ({path})")
        r = run_suite(label, path)
        results.append(r)
        total_passed += r["passed"]
        total_failed += r["failed"]
        status = "[PASS]" if r["returncode"] == 0 else "[FAIL]"
        if r["returncode"] != 0:
            all_ok = False
        print(f"  {status}  {r['passed']} passed / {r['failed']} failed  ({r['elapsed_s']}s)")
        print(f"  {r['summary']}")
        if r["returncode"] != 0:
            print("  --- stdout tail ---")
            print(r["stdout_tail"])

    # snapshot 스크립트 직접 실행 (pytest 미사용 — PYTHONPATH=ROOT 필요)
    print(f"\n▶ snapshot ({SNAPSHOT_SCRIPT})")
    t0 = time.time()
    import os as _os
    snap_env = {**_os.environ, "PYTHONPATH": str(ROOT)}
    snap_result = subprocess.run(
        [sys.executable, SNAPSHOT_SCRIPT],
        capture_output=True, cwd=str(ROOT), env=snap_env,
    )
    snap_elapsed = round(time.time() - t0, 2)
    snap_ok = snap_result.returncode == 0
    snap_label = "[PASS]" if snap_ok else "[FAIL]"
    if not snap_ok:
        all_ok = False
    print(f"  {snap_label}  ({snap_elapsed}s)")
    snap_entry = {
        "label": "snapshot", "path": SNAPSHOT_SCRIPT,
        "passed": 0, "failed": 0,
        "returncode": snap_result.returncode, "elapsed_s": snap_elapsed,
        "summary": "snapshot script OK" if snap_ok else "snapshot script FAIL",
        "stdout_tail": (snap_result.stdout or b"")[-400:].decode("utf-8", errors="replace"),
    }
    results.append(snap_entry)

    total_elapsed = round(time.time() - t_start, 2)

    print("\n" + "=" * 72)
    print(f"Total: {total_passed} passed / {total_failed} failed  ({total_elapsed}s)")
    print("Result:", "ALL PASS" if all_ok else "FAIL")
    print("=" * 72)

    if not no_report:
        report = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total_passed": total_passed,
            "total_failed": total_failed,
            "total_elapsed_s": total_elapsed,
            "all_pass": all_ok,
            "suites": results,
        }
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Report: {REPORT_PATH}")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
