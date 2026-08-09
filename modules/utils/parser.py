# -*- coding: utf-8 -*-
"""
modules/utils/parser.py — LLM 응답 JSON 파싱 공통 유틸 (v12 정규 위치)

LLM이 순수 JSON 대신 ```json ... ``` 코드블록이나 앞뒤 설명문을 섞어
반환해도 안전하게 dict로 파싱한다.
(기존 strategy_room._parse_json_lenient 로직을 공통화 — modules/json_utils.py 는
 하위호환 재노출 shim)
"""
import json
import logging
import re

_LOG = logging.getLogger("pipeline")


def parse_json_lenient(text: str) -> dict:
    """LLM 응답에서 JSON 객체만 안전하게 추출.

    - 빈 응답 방어 (ValueError)
    - ```json ... ``` / ``` ... ``` 코드블록 펜스 제거
    - 펜스 제거 후 빈 문자열 방어 (2차 가드)
    - 앞뒤 설명문이 섞여도 첫 '{' ~ 마지막 '}' 구간만 파싱

    실패 시 json.JSONDecodeError 또는 ValueError 를 raise 한다.
    """
    if not text or not text.strip():
        raise ValueError("LLM이 빈 응답을 반환했습니다")
    s = text.strip()
    s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
    s = re.sub(r"\s*```$", "", s).strip()
    # 2차 가드: 펜스 제거 후 빈 문자열 (예: LLM이 ```json\n``` 반환)
    if not s:
        _LOG.warning("parse_json_lenient: 펜스 제거 후 빈 응답. 원본(앞50): %r", text[:50])
        raise ValueError(
            f"AI 응답이 비어있거나 JSON 형식이 아닙니다 (원본 앞부분: {text[:80]!r})"
        )
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        start, end = s.find("{"), s.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(s[start:end + 1])
        # {..} 블록 없음 — 비JSON 텍스트(거부 메시지 등) → 명확한 메시지로 재raise
        _LOG.warning(
            "parse_json_lenient: JSON 추출 실패. 원본 앞100자: %r", text[:100]
        )
        raise ValueError(
            f"AI가 JSON 형식이 아닌 응답을 반환했습니다 (원본 앞부분: {text[:80]!r})"
        ) from None


def try_parse_json(text: str, default=None) -> dict:
    """parse_json_lenient 의 예외 무던화 버전. 실패 시 default 반환."""
    try:
        return parse_json_lenient(text)
    except (ValueError, json.JSONDecodeError):
        return default if default is not None else {}
