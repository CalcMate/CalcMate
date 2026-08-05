import subprocess
import sys
import json
import time
from pathlib import Path
import argparse
import os

# Add the project root to the Python path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from modules.registry_loader import find_impacted, load_registry_v3, calculator_name
from modules.telegram_notifier import send_success, send_failure, send_warning
from scripts.run_regression import run_suite, SUITES, SNAPSHOT_SCRIPT # Import necessary components from run_regression.py

REPORT_PATH = ROOT / "docs" / "regression_report.json"
AUDIT_PATH = ROOT / "LEGAL_BASIS_AUDIT.md"
MASTER_YAML_PATH = ROOT / "docs" / "legal_basis.master.yaml"

def get_changed_entity_ids(previous_master_content: str, current_master_content: str) -> list[str]:
    """
    Compares two versions of master.yaml content and returns a list of entity IDs that have changed.
    This is a placeholder for actual diffing logic. For now, we'll assume the entire file changed
    if the content is different. In a real scenario, a YAML diff library would be used.
    """
    # This is a simplified change detection. In a real scenario, you'd parse YAML
    # and compare specific entity entries.
    if previous_master_content != current_master_content:
        # For now, if anything in master.yaml changes, we'll consider all entities potentially impacted.
        # A more sophisticated approach would involve parsing the YAML and identifying
        # which specific entity_ids (top-level keys) have been modified.
        # For the purpose of this task, we'll return all entity_ids from the current master.
        import yaml
        current_data = yaml.safe_load(current_master_content)
        if current_data and isinstance(current_data, dict):
            # Exclude schema_version from entity IDs
            return [key for key in current_data.keys() if key != "schema_version"]
    return []

def run_regression_for_impacted(impacted_slugs: list[str]):
    """Runs regression tests only for the impacted calculators."""
    print("\n" + "=" * 72)
    print(f"[REGRESSION] Running tests for {len(impacted_slugs)} impacted calculators")
    print("=" * 72)

    results = []
    total_passed = 0
    total_failed = 0
    all_ok = True
    warnings = []
    t_start = time.time()

    # Map slugs to their corresponding test suites
    slug_to_suite_map = {
        "weekly-holiday-allowance": "weekly_holiday",
        "severance-pay": "severance",
        "unemployment-benefit": "unemployment",
        "four-insurances": "four_insurances",
        "annual-leave-allowance": "annual_leave",
        "parental-leave-allowance": "parental_leave", # Assuming this slug for parental leave
        "income-tax-calculator": "income_tax", # Assuming this slug for income tax
        "연말정산_환급액_계산기": "income_tax", # Map Korean slug to income_tax test
        "육아휴직_급여_계산기": "parental_leave", # Map Korean slug to parental_leave test
    }

    # Collect unique test paths for impacted slugs
    test_paths_to_run = set()
    for slug in impacted_slugs:
        suite_label = slug_to_suite_map.get(slug)
        if suite_label:
            for label, path in SUITES:
                if label == suite_label:
                    test_paths_to_run.add((label, path))
                    break
        else:
            warning_msg = f"No test suite found for impacted slug: {slug}"
            print(f"  [WARNING] {warning_msg}")
            warnings.append(warning_msg)

    # Always include invariants if any calculator is impacted
    for label, path in SUITES:
        if label == "invariants":
            test_paths_to_run.add((label, path))
            break

    if not test_paths_to_run:
        print("  No specific test suites found for impacted calculators. Exiting regression.")
        return True, {}, warnings # Return True for all_ok if no tests were run

    for label, path in test_paths_to_run:
        print("\n▶ " + label + " (" + path + ")")
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

    # Always run snapshot script if it's part of the original regression
    print("\n▶ snapshot (" + SNAPSHOT_SCRIPT + ")")
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

    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "slug": impacted_slugs[0] if impacted_slugs else "N/A", # Assuming single slug for now, or first
        "affected": impacted_slugs,
        "passed": total_passed,
        "failed": total_failed,
        "result": "PASS" if all_ok else "FAIL",
        "total_elapsed_s": total_elapsed,
        "suites": results,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Report: {REPORT_PATH}")

    return all_ok, report, warnings

def update_audit_log(report: dict):
    """Appends the regression result to the audit log."""
    date_str = time.strftime("%Y-%m-%d")
    result_str = "Regression PASS" if report["result"] == "PASS" else "Regression FAIL"
    num_calcs = len(report["affected"])
    log_entry = f"{date_str} PROMOTED {result_str} {num_calcs} Calculators\n"

    with open(AUDIT_PATH, "a", encoding="utf-8") as f:
        f.write(log_entry)
    print(f"Audit log updated: {AUDIT_PATH}")

def main():
    parser = argparse.ArgumentParser(description="RMS Automatic Regression Runner")
    parser.add_argument("--slug", type=str, help="Run regression for a specific slug (for testing purposes).")
    args = parser.parse_args()
    
    # Load cfg
    from modules.config_loader import load_config
    cfg = load_config(str(ROOT / "config" / "config.yaml"))

    print("====================")
    print("RMS Regression")
    print("====================")

    current_master_content = MASTER_YAML_PATH.read_text(encoding="utf-8")
    
    changed_entity_ids = []
    if args.slug:
        changed_entity_ids = [args.slug]
        print(f"Simulating change for entity ID: {args.slug}")
    else:
        print("No specific slug provided. Assuming master.yaml has changed and identifying all potential impacts.")
        import yaml
        current_data = yaml.safe_load(current_master_content)
        if current_data and isinstance(current_data, dict):
            changed_entity_ids = [key for key in current_data.keys() if key != "schema_version"]

    if not changed_entity_ids:
        print("No changes detected in master.yaml or no specific slug provided for testing. Exiting.")
        sys.exit(0)

    print(f"Changed entity IDs: {changed_entity_ids}")

    impacted_slugs = []
    registry_v3 = load_registry_v3() # Load the registry once

    for entity_id in changed_entity_ids:
        # 1. Check if the changed entity_id is itself a calculator slug in the registry
        if entity_id in registry_v3:
            impacted_slugs.append(entity_id)
        
        # 2. Find other calculators that reference this entity_id in their legal_refs
        impacted_slugs.extend(find_impacted(entity_id))
    
    # Ensure unique slugs
    impacted_slugs = list(set(impacted_slugs))

    if not impacted_slugs:
        print("No calculators impacted by the changes. Exiting.")
        sys.exit(0)

    print("\nChanged:")
    for entity_id in changed_entity_ids:
        print(f"- {entity_id}")

    print("\nAffected:")
    for slug in impacted_slugs:
        print(f"- {calculator_name(slug)} ({slug})")

    # G5-2 & G5-3: Run regression and save report
    all_tests_passed, report, warnings = run_regression_for_impacted(impacted_slugs)

    if warnings:
        send_warning(cfg, f"Warnings: {len(warnings)} issues - " + ", ".join(warnings))

    # G5-4: Promotion blocking
    print("\nPromotion:")
    if all_tests_passed:
        print("ALLOWED")
        send_success(cfg, f"Regression PASSED: {len(report['affected'])} calculators")
    else:
        print("BLOCKED")
        send_failure(cfg, f"Regression FAILED: {len(report['affected'])} calculators")
        sys.exit(1) # Block promotion by exiting with a non-zero status

    # G5-5: Audit logging
    update_audit_log(report)

    print("\n====================")

if __name__ == "__main__":
    main()
