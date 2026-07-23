# -*- coding: utf-8 -*-
"""scripts/rms_impact.py — G-3 영향 계산기 분석 (Phase G-3)

법령 필드값이 변경될 때 어느 계산기가 영향을 받는지 출력.

사용:
  python -m scripts.rms_impact                          # 전체 매핑 테이블 출력
  python -m scripts.rms_impact --field np_rate          # 특정 필드 영향 조회
  python -m scripts.rms_impact --field np_rate hi_rate  # 복수 필드
"""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import argparse
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BASE))

from modules.rms import IMPACT_MAP, find_impacted, impact_report


def cmd_all() -> None:
    print("=== G-3 영향 계산기 매핑 테이블 ===\n")
    # 역매핑: slug → 참조하는 법령 필드들
    by_slug: dict[str, list[str]] = {}
    for field, slugs in IMPACT_MAP.items():
        for s in slugs:
            by_slug.setdefault(s, []).append(field)

    print(f"{'법령 필드':<35} {'영향 계산기'}")
    print("-" * 75)
    for field, slugs in sorted(IMPACT_MAP.items()):
        print(f"  {field:<33} {', '.join(slugs)}")

    print()
    print(f"{'계산기 slug':<42} {'참조 법령 필드'}")
    print("-" * 75)
    for slug, fields in sorted(by_slug.items()):
        print(f"  {slug:<40} {', '.join(fields)}")


def cmd_field(fields: list[str]) -> None:
    for f in fields:
        impacted = find_impacted(f)
        print(f"필드: {f}")
        if impacted:
            for s in impacted:
                print(f"  → {s}")
        else:
            print("  영향받는 계산기 없음 (IMPACT_MAP에 미등록)")
        print()


def main():
    parser = argparse.ArgumentParser(description="G-3 영향 계산기 분석")
    parser.add_argument("--field", nargs="+", help="분석할 법령 필드명(들)")
    args = parser.parse_args()

    if args.field:
        cmd_field(args.field)
    else:
        cmd_all()


if __name__ == "__main__":
    main()
