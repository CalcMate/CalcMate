# -*- coding: utf-8 -*-
"""scripts/rms_promote.py — RMS 승격 CLI (Phase G-4)

사용:
  python -m scripts.rms_promote <slug>                  # draft → master 승격
  python -m scripts.rms_promote <slug> --approve        # APPROVED 상태로 전환 (promote 전 단계)
  python -m scripts.rms_promote <slug> --source "출처URL"
  python -m scripts.rms_promote --status                # 모든 draft 항목 상태 출력
  python -m scripts.rms_promote --skip-regression       # 회귀 테스트 없이 강제 승격 (비상용)

워크플로: DETECTED → DRAFT → [--approve] → APPROVED → [promote] → PROMOTED
"""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

import argparse
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BASE))

from modules.rms import promote, approve_draft, _read_yaml, _DRAFT, _MASTER, find_impacted


def cmd_status() -> None:
    draft = _read_yaml(_DRAFT)
    master = _read_yaml(_MASTER)
    if not draft:
        print("draft.yaml 에 항목 없음 (변경 감지된 법령 없음)")
        return
    print(f"{'slug':<40} {'rms_status':<16} {'감지일':<12} {'변경 필드'}")
    print("-" * 90)
    for slug, entry in sorted(draft.items()):
        if isinstance(entry, dict) and "rms_status" in entry:
            status = entry.get("rms_status", "-")
            detected = entry.get("rms_detected", "-")
            changes = list((entry.get("rms_changes") or {}).keys())
            print(f"{slug:<40} {status:<16} {detected:<12} {changes}")


def cmd_promote(slug: str, source: str, skip_regression: bool) -> None:
    print(f"[rms_promote] '{slug}' 승격 시작 ...")
    if not skip_regression:
        print("  → 회귀 테스트 실행 중 (약 10초) ...")
    result = promote(slug, source=source, skip_regression=skip_regression)
    status = result["status"]
    msg = result["message"]
    marker = "OK" if status == "PROMOTED" else "NG"
    print(f"  [{marker}] {status}: {msg}")
    if status == "PROMOTED":
        print()
        print(f"  영향 계산기: {', '.join(find_impacted(slug)) or '없음'}")
        print("  → LEGAL_BASIS_AUDIT.md 기록 완료")
        print("  → archive/{year}.yaml 스냅샷 갱신 완료")


def cmd_approve(slug: str, approver: str) -> None:
    result = approve_draft(slug, approver=approver)
    status = result["status"]
    print(f"  [{status}] {result['message']}")


def main():
    parser = argparse.ArgumentParser(description="RMS 승격 CLI")
    parser.add_argument("slug", nargs="?", help="계산기 slug")
    parser.add_argument("--approve", action="store_true", help="APPROVED 상태 전환")
    parser.add_argument("--source", default="", help="법령 출처 URL/명칭")
    parser.add_argument("--approver", default="운영자", help="승인자 이름")
    parser.add_argument("--status", action="store_true", help="draft 항목 상태 출력")
    parser.add_argument("--skip-regression", action="store_true", help="회귀 테스트 생략(비상용)")
    args = parser.parse_args()

    if args.status:
        cmd_status()
        return

    if not args.slug:
        parser.print_help()
        sys.exit(1)

    if args.approve:
        cmd_approve(args.slug, args.approver)
    else:
        cmd_promote(args.slug, source=args.source, skip_regression=args.skip_regression)


if __name__ == "__main__":
    main()
