# -*- coding: utf-8 -*-
"""scripts/rms_check.py — G-2 법령 변경 수동 점검 체크리스트 + DRAFT 자동 생성 (Phase G-2/G-8)

점검 대상 (매년 확인):
  - 최저임금 (매년 8월 결정, 익년 1월 적용)
  - 4대보험 요율 (국민연금 7월, 건강보험 1월)
  - 소득세 구간 (비정기)
  - 구직급여 상한 (매년 확인)
  - 육아휴직 급여 상/하한 (시행령 개정 시)

사용:
  python -m scripts.rms_check                  # 현재값 출력 + 점검 항목 안내
  python -m scripts.rms_check --draft <slug> --field <field> --new-value <value> --source <url>
"""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import argparse
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BASE))

from modules.rms import _read_yaml, _MASTER, create_draft, find_impacted


# 점검 대상 정의 (field_path: dot-notation)
CHECK_ITEMS = [
    {
        "name": "최저임금 (시간급)",
        "slug": "unemployment-benefit",
        "field": "benefit_amounts.min_wage_hourly",
        "current_path": ("benefit_amounts", "min_wage_hourly"),
        "note": "고용노동부 고시 — 매년 8월 결정, 익년 1월 1일 적용\n"
                "확인: https://www.moel.go.kr (최저임금위원회 고시)",
        "also_impacts": ["weekly-holiday-allowance"],
    },
    {
        "name": "국민연금 요율 (근로자)",
        "slug": "four-insurances",
        "field": "insurance_rates.np_rate",
        "current_path": ("insurance_rates", "np_rate"),
        "note": "국민연금법 제88조 — 현재 4.5% (총 9%의 근로자 절반)\n"
                "확인: https://www.nps.or.kr",
    },
    {
        "name": "국민연금 기준소득월액 상한",
        "slug": "four-insurances",
        "field": "insurance_rates.np_max",
        "current_path": ("insurance_rates", "np_max"),
        "note": "매년 7월 1일 조정 (보건복지부 고시)\n"
                "확인: https://www.nps.or.kr",
    },
    {
        "name": "국민연금 기준소득월액 하한",
        "slug": "four-insurances",
        "field": "insurance_rates.np_min",
        "current_path": ("insurance_rates", "np_min"),
        "note": "매년 7월 1일 조정 (보건복지부 고시)",
    },
    {
        "name": "건강보험 요율 (근로자)",
        "slug": "four-insurances",
        "field": "insurance_rates.hi_rate",
        "current_path": ("insurance_rates", "hi_rate"),
        "note": "매년 1월 1일 조정 (건강보험공단)\n"
                "확인: https://www.nhis.or.kr",
    },
    {
        "name": "장기요양보험 요율 (건강보험료 × %)",
        "slug": "four-insurances",
        "field": "insurance_rates.ltc_rate",
        "current_path": ("insurance_rates", "ltc_rate"),
        "note": "매년 1월 1일 조정 (건강보험공단)",
    },
    {
        "name": "고용보험 요율 (근로자)",
        "slug": "four-insurances",
        "field": "insurance_rates.ei_rate",
        "current_path": ("insurance_rates", "ei_rate"),
        "note": "매년 1월 1일 기준 (고용노동부)\n"
                "확인: https://www.moel.go.kr",
    },
    {
        "name": "구직급여 일 상한액",
        "slug": "unemployment-benefit",
        "field": "benefit_amounts.daily_max",
        "current_path": ("benefit_amounts", "daily_max"),
        "note": "고용노동부 고시 — 2019년 이후 66,000원 유지\n"
                "확인: https://www.ei.go.kr",
    },
    {
        "name": "육아휴직 급여 상/하한 (일반)",
        "slug": "육아휴직_급여_계산기",
        "field": "parental_leave_benefit.general.ceiling",
        "current_path": ("parental_leave_benefit", "general", "ceiling"),
        "note": "고용보험법 시행령 제95조 — 매년 확인 필요\n"
                "확인: https://www.moel.go.kr",
    },
]


def _get_nested(data: dict, path: tuple) -> object:
    cur = data
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def cmd_show() -> None:
    master = _read_yaml(_MASTER)
    print("=== RMS 법령 변경 점검 체크리스트 ===")
    print(f"master.yaml 기준 현재값\n")
    for item in CHECK_ITEMS:
        entry = master.get(item["slug"], {})
        value = _get_nested(entry, item["current_path"])
        impacted = find_impacted(item["field"].split(".")[-1])
        print(f"[{item['name']}]")
        print(f"  slug   : {item['slug']} / field: {item['field']}")
        print(f"  현재값 : {value}")
        print(f"  영향   : {', '.join(impacted) or '없음'}")
        print(f"  안내   : {item['note']}")
        print()
    print("변경 발견 시:")
    print("  python -m scripts.rms_check --draft <slug> --field <field.path> --new-value <value> --source <url>")


def cmd_draft(slug: str, field: str, new_value: str, source: str) -> None:
    try:
        parsed_val = int(new_value) if "." not in new_value else float(new_value)
    except ValueError:
        parsed_val = new_value
    result = create_draft(slug, {field: parsed_val}, source=source)
    print(f"[{result['status']}] {result['message']}")
    print()
    impacted = find_impacted(field.split(".")[-1])
    if impacted:
        print(f"영향 계산기: {', '.join(impacted)}")
    print()
    print("다음 단계:")
    print(f"  1. docs/legal_basis.draft.yaml 에서 '{slug}' 항목 내용 확인")
    print(f"  2. python -m scripts.rms_promote {slug} --approve --source \"{source}\"")
    print(f"  3. python -m scripts.rms_promote {slug} --source \"{source}\"")


def main():
    parser = argparse.ArgumentParser(description="RMS 법령 변경 점검")
    parser.add_argument("--draft", metavar="SLUG", help="DRAFT 생성할 slug")
    parser.add_argument("--field", help="변경할 필드 (dot-notation, 예: benefit_amounts.daily_max)")
    parser.add_argument("--new-value", help="새 값")
    parser.add_argument("--source", default="", help="법령 출처 URL/명칭")
    args = parser.parse_args()

    if args.draft:
        if not args.field or args.new_value is None:
            print("오류: --draft 사용 시 --field 와 --new-value 필수")
            sys.exit(1)
        cmd_draft(args.draft, args.field, args.new_value, args.source)
    else:
        cmd_show()


if __name__ == "__main__":
    main()
