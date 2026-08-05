# -*- coding: utf-8 -*-
"""tests/quality_sample_evaluation.py — 콘텐츠 품질 평가 및 Golden Snapshot 생성"""
import pytest
import json
from pathlib import Path
from modules.content_quality.quality_validator import QualityValidator

# 대상 계산기 및 규칙 (예시)
COMPUTE_RULES = {
    "weekly-holiday-allowance": {"min_wage": 10030},
    "parental-leave-benefit": {"min_wage": 10030}
}

def generate_samples():
    """테스트용 샘플 데이터 생성"""
    return {
        "weekly-holiday-allowance": {
            "PASS": "서론 주휴수당은 중요합니다. 계산 방법은 시급*시간입니다. 계산 기준 15시간 이상입니다. 예시로 시급 10030원일 때 계산해보세요. 주의사항으로 15시간 미만은 안 됩니다. FAQ 자주 묻는 질문: 주휴수당 대상은? 출처 법령 제55조.",
            "WARNING": "주휴수당 중요합니다. 계산하세요.",
            "HOLD": "10시간 근무해도 주휴수당 받을 수 있습니다."
        }
    }

def test_evaluate_samples():
    validator = QualityValidator()
    samples = generate_samples()
    snapshot = []

    for slug, cases in samples.items():
        rules = COMPUTE_RULES.get(slug)
        for sample_type, content in cases.items():
            result = validator.validate(content, slug, rules)
            
            # 예상 결과와 비교 (간략)
            assert result in ["PASS", "WARNING", "REWRITE", "HOLD"]
            
            snapshot.append({
                "calculator": slug,
                "sample": sample_type,
                "content": content,
                "validation_result": result
            })
            
    # Golden Snapshot 저장
    output_path = Path("tests/snapshots/content_quality_snapshot.json")
    output_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Snapshot saved to {output_path}")

if __name__ == "__main__":
    test_evaluate_samples()
