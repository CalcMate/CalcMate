# -*- coding: utf-8 -*-
"""
modules/slug_generator.py — 계산기 이름 → 영문 slug 자동 생성

규칙:
  - 소문자, 하이픈(-) 구분, 영문/숫자/하이픈만 허용
  - 앞뒤 하이픈 제거, 중복 하이픈 제거
  - 알려진 한국어 노무/급여 용어는 lookup table로 직접 매핑
  - 미등록 용어는 숫자·영문 부분을 추출해 최대한 의미있는 slug 생성
"""
import re

# 한국어 계산기 이름 → 영문 slug 매핑 (우선순위: 긴 문자열부터 매칭)
_KO_SLUG_MAP: dict[str, str] = {
    # ── 핵심 급여/수당 ──────────────────────────────────────────
    "주휴수당":          "weekly-pay",
    "주휴":             "weekly-pay",
    "실업급여":          "unemployment-benefit",
    "실업":             "unemployment",
    "퇴직금":           "severance-pay",
    "퇴직":             "severance",
    "연차수당":          "annual-leave",
    "연차":             "annual-leave",
    "연봉":             "annual-salary",
    "월급 실수령액":      "salary",
    "월급실수령액":       "salary",
    "실수령액":          "take-home",
    "월급":             "salary",
    "시급":             "hourly-wage",
    "일급":             "daily-wage",
    "야간수당":          "night-shift",
    "연장수당":          "overtime",
    "연장근로수당":       "overtime",
    "초과근무수당":       "overtime",

    # ── 4대보험 ─────────────────────────────────────────────────
    "4대보험":           "four-insurances",
    "사대보험":          "four-insurances",
    "국민연금":          "national-pension",
    "건강보험":          "health-insurance",
    "고용보험":          "employment-insurance",
    "산재보험":          "industrial-insurance",
    "장기요양보험":       "long-term-care",

    # ── 세금 ────────────────────────────────────────────────────
    "소득세":           "income-tax",
    "연말정산":          "year-end-tax",
    "근로소득세":         "wage-tax",
    "종합소득세":         "comprehensive-tax",
    "부가세":           "vat",
    "부가가치세":         "vat",

    # ── 휴가/휴직 ────────────────────────────────────────────────
    "육아휴직 급여":      "parental-leave-benefit",
    "육아휴직급여":       "parental-leave-benefit",
    "육아휴직":          "parental-leave",
    "출산휴가":          "maternity-leave",
    "배우자 출산휴가":    "paternity-leave",
    "배우자출산휴가":     "paternity-leave",

    # ── 근로 조건 ────────────────────────────────────────────────
    "최저임금":          "minimum-wage",
    "주 52시간":         "52-hour",
    "52시간":           "52-hour",
    "통상임금":          "ordinary-wage",
    "평균임금":          "average-wage",

    # ── 퇴직/연금 ────────────────────────────────────────────────
    "퇴직연금":          "retirement-pension",
    "연금":             "pension",

    # ── 복리후생/기타 ─────────────────────────────────────────────
    "식대":             "meal-allowance",
    "교통비":           "commute-allowance",
    "출장비":           "business-trip",
    "복직":             "reinstatement",
}

# 매핑 길이 내림차순 정렬 (긴 문자열 먼저 매칭되도록)
_SORTED_KEYS = sorted(_KO_SLUG_MAP.keys(), key=len, reverse=True)


def _normalize_slug(s: str) -> str:
    """영문/숫자만 남기고 하이픈 정리."""
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s)
    return s.strip("-")


def generate_slug(name: str) -> str:
    """계산기 이름 → 영문 slug 자동 생성.

    Args:
        name: 계산기 이름 (예: "주휴수당 계산기")

    Returns:
        영문 slug (예: "weekly-pay"), 생성 불가 시 ""
    """
    if not name or not isinstance(name, str):
        return ""

    # 공통 접미사 제거 ("계산기", "계산")
    cleaned = re.sub(r"\s*(계산기|계산)\s*$", "", name.strip())
    cleaned = cleaned.strip()

    if not cleaned:
        return ""

    # 1순위: 전체 이름 직접 매핑 (정확 일치)
    if cleaned in _KO_SLUG_MAP:
        return _KO_SLUG_MAP[cleaned]

    # 2순위: 부분 매핑 — 이름에서 알려진 용어를 찾아 치환 후 조합
    result_parts: list[str] = []
    remaining = cleaned
    while remaining:
        matched = False
        for key in _SORTED_KEYS:
            if remaining.startswith(key):
                result_parts.append(_KO_SLUG_MAP[key])
                remaining = remaining[len(key):].lstrip()
                matched = True
                break
        if not matched:
            # 첫 단어(공백·특수문자 전까지) 소비 — 영문/숫자면 그대로, 한글이면 건너뜀
            m = re.match(r"([a-zA-Z0-9]+)(.*)", remaining)
            if m:
                result_parts.append(m.group(1).lower())
                remaining = m.group(2).lstrip()
            else:
                # 한 글자 소비 (한글 등)
                remaining = remaining[1:].lstrip()

    slug = "-".join(p for p in result_parts if p)
    if slug:
        return _normalize_slug(slug)

    # 3순위: 이름에서 영문·숫자 부분만 추출
    extracted = re.sub(r"[^a-zA-Z0-9]+", "-", cleaned)
    extracted = _normalize_slug(extracted)
    return extracted  # 빈 문자열이면 "" 반환
