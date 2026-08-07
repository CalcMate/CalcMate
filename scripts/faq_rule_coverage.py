# -*- coding: utf-8 -*-
"""scripts/faq_rule_coverage.py — 계산기별 FAQ Validator 규칙 커버리지 분석"""
import yaml
from pathlib import Path

# 슬러그 매핑 (Registry 엔트리 키와 실제 slug 확인용)
CALCULATORS = [
    "unemployment-benefit",
    "육아휴직_급여_계산기",
    "four-insurances",
    "weekly-holiday-allowance",
    "severance-pay",
    "annual-leave-allowance",
    "연말정산_환급액_계산기"
]

def analyze_coverage():
    base_dir = Path(__file__).resolve().parent.parent
    registry_dir = base_dir / "docs" / "registry"
    
    report = {}
    
    # 1. 계산기별 규칙 추출
    for calc_slug in CALCULATORS:
        report[calc_slug] = {
            "threshold_rule": False,
            "numeric_rule": False,
            "condition_rule": False,
            "exception_rule": False
        }
        # 레지스트리 파일에서 조건 정보 탐색 (간략화)
        for f in registry_dir.glob("*.yaml"):
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if calc_slug in data:
                entry = data[calc_slug]
                # compute_rules 기반 판별 (시뮬레이션)
                rules = str(entry).lower()
                if "min_" in rules or "threshold" in rules: report[calc_slug]["threshold_rule"] = True
                if "limit" in rules or "max" in rules or "rate" in rules: report[calc_slug]["numeric_rule"] = True
                if "condition" in rules or "if" in rules: report[calc_slug]["condition_rule"] = True
                if "exception" in rules or "not" in rules: report[calc_slug]["exception_rule"] = True
                
    return report

def generate_report(report):
    output = "# RULE_COVERAGE_REPORT.md\n\n"
    for slug, rules in report.items():
        output += f"## {slug}\n"
        for rule, supported in rules.items():
            output += f"{'✓' if supported else '✗'} {rule}\n"
        output += "\n"
    
    Path("docs/RULE_COVERAGE_REPORT.md").write_text(output, encoding="utf-8")
    print(output)

if __name__ == "__main__":
    report = analyze_coverage()
    generate_report(report)
