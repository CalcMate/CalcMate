# -*- coding: utf-8 -*-
"""tests/test_app_factory_card_desc_truncation.py — App Factory card_desc 생성 회귀 테스트

배경: modules/app_factory.py의 _build_v3_entry()가 card_desc를 desc[:45]로
단순 절단하여 단어 중간에서 문장이 잘리는 버그가 있었다(2026-08 발견).
_make_card_desc() 헬퍼로 교체하여 문장 경계 우선, 실패 시 단어 경계에서
절단하도록 수정했다. 이 테스트는 그 변환 로직 자체를 직접 검증한다.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.app_factory import _make_card_desc, _CARD_DESC_MAX


def test_short_sentence_returned_as_is():
    """45자 이하 문장은 그대로 반환된다."""
    desc = "체중 상태를 확인할 수 있습니다."
    assert len(desc) <= _CARD_DESC_MAX
    assert _make_card_desc(desc) == desc


def test_exactly_max_length_returned_as_is():
    """정확히 45자인 문장은 그대로 반환된다(절단/ellipsis 없음)."""
    desc = "가" * _CARD_DESC_MAX
    assert len(desc) == _CARD_DESC_MAX
    out = _make_card_desc(desc)
    assert out == desc
    assert "…" not in out


def test_first_sentence_within_limit_used_whole():
    """전체 desc는 45자를 넘지만 첫 문장이 45자 이내면 첫 문장 전체를 그대로 사용한다."""
    first_sentence = "자동차 취등록세를 간편하게 계산할 수 있습니다."
    desc = first_sentence + " 이후 등록 절차도 함께 안내합니다."
    assert len(first_sentence) <= _CARD_DESC_MAX
    assert len(desc) > _CARD_DESC_MAX
    out = _make_card_desc(desc)
    assert out == first_sentence
    assert "…" not in out


def test_first_sentence_too_long_no_mid_word_cut():
    """첫 문장 자체가 45자를 초과하면 단어 중간을 자르지 않고 마지막 완전한
    단어까지만 남긴 뒤 ellipsis를 붙인다."""
    desc = "이 계산기는 매우 길고 복잡한 설명을 담고 있어서 첫 문장 자체가 사십오자를 훌쩍 넘어가는 극단적인 경우를 시험합니다"
    out = _make_card_desc(desc)
    assert len(out) <= _CARD_DESC_MAX + 1  # 절단 텍스트 + '…' 1글자
    assert out.endswith("…")
    body = out[:-1]
    # 잘린 본문이 원문의 완전한 접두 부분(단어 경계)과 일치해야 한다 — 단어 중간 절단 금지
    assert desc.startswith(body)
    assert not desc[len(body):len(body) + 1].strip() or desc[len(body)] == " "


def test_long_sentence_cuts_at_last_complete_word():
    """공백이 있는 긴 문장은 마지막 완전한 단어 뒤에서 절단된다."""
    desc = "사용자가 차량의 종류 가격 지역 등을 입력하면 자동차를 구매할 때 필요한 취득세와 등록세를 계산합니다"
    out = _make_card_desc(desc)
    assert out.endswith("…")
    body = out[:-1]
    assert desc.startswith(body)
    # body가 desc 안에서 단어(공백) 경계에서 끝나야 한다
    assert body == "" or desc[len(body)] == " " or len(body) == len(desc)


def test_no_punctuation_long_text_word_boundary_fallback():
    """문장부호 없는 긴 설명은(공백이 있다면) 단어 경계에서 절단된다."""
    desc = "사용자 입력값을 받아 계산 결과를 즉시 화면에 표시해주는 매우 편리한 신규 계산기 도구입니다 계속해서 더 많은 설명이 이어집니다"
    assert len(desc) > _CARD_DESC_MAX
    out = _make_card_desc(desc)
    assert out.endswith("…")
    body = out[:-1]
    assert desc.startswith(body)
    assert len(out) <= _CARD_DESC_MAX + 1


def test_existing_ellipsis_no_duplicate():
    """절단 경계 직전에 이미 '…'가 있으면 중복 ellipsis 없이 하나만 남는다."""
    desc = "이 설명은 이미 줄임표가 포함되어 있습니다… 그 뒤에도 내용이 계속 이어집니다"
    out = _make_card_desc(desc)
    assert out.count("…") == 1
    assert not out.endswith("……")
    assert "…familia" not in out  # sanity: no corruption


def test_empty_and_none_desc_returns_empty():
    """빈 문자열/None 입력은 예외 없이 빈 문자열을 반환한다."""
    assert _make_card_desc("") == ""
    assert _make_card_desc(None) == ""
