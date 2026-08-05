# -*- coding: utf-8 -*-
import pytest
from modules.content_quality.intent_analyzer import IntentAnalyzer
from modules.content_quality.information_density import InformationDensity
from modules.content_quality.eeat_checker import EEATChecker
from modules.content_quality.structure_checker import StructureChecker
from modules.content_quality.example_checker import ExampleChecker
from modules.content_quality.faq_position_checker import FAQPositionChecker
from modules.content_quality.quality_validator import QualityValidator

def test_intent_analyzer():
    analyzer = IntentAnalyzer()
    content = "계산방법 지급조건 계산예시"
    score, missing = analyzer.analyze(content, "weekly-holiday-allowance")
    assert score == 100
    assert len(missing) == 0

def test_information_density():
    density = InformationDensity()
    content = "계산 기준 주의사항 예시"
    score, missing = density.evaluate(content)
    assert score == 100
    assert len(missing) == 0

def test_eeat_checker():
    checker = EEATChecker()
    content = "예시 법령 출처 주의사항"
    passed, findings = checker.check(content)
    assert passed is True

def test_structure_checker():
    checker = StructureChecker()
    content = "서론 계산 방법 주의사항 FAQ"
    passed, missing = checker.check(content)
    assert passed is True

def test_example_checker():
    checker = ExampleChecker()
    rules = {"min_wage": 10030}
    content = "시급 10030원으로 계산합니다."
    is_valid, msg = checker.check(content, rules, "min_wage", "weekly-holiday-allowance")
    assert is_valid is True

def test_faq_position_checker():
    checker = FAQPositionChecker()
    content = "초반 내용" * 10 + "FAQ"
    status, msg = checker.check(content)
    assert status == "PASS"

def test_quality_validator_hold():
    validator = QualityValidator()
    # 법령 오류 케이스
    content = "안녕"
    rules = {"min_wage": 99999} # 불일치
    status = validator.validate(content, "weekly-holiday-allowance", rules)
    assert status == "HOLD"
