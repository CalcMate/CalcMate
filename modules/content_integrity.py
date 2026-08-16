# -*- coding: utf-8 -*-
"""
Phase 5-E 자동 정합성 검증 게이트

G-CALC   : 검증된 예시 result 값 vs 본문 서술 정합성
G-NUMCON : 본문 내 명시적 산술식 오류 검출
G-LEGAL  : 법적 근거 오인용 / 무관 키워드 검출
G-STYLE+ : AI 문체 잔존 강화 검사 (G7 보완)
"""
from __future__ import annotations
import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from modules.publish_quality import _plain_text as _strip_html


# ═══════════════════════════════════════════════════════════════════════════
# 공통 유틸리티
# ═══════════════════════════════════════════════════════════════════════════

def _format_krw(amount: int) -> list[str]:
    """
    정수 원화 금액 → 본문에서 검색 가능한 표기 변형 목록.
    14400000 → ['1,440만원', '1,440만 원', '1440만원', ...]
    105600   → ['105,600원', '105600원']
    """
    variants: list[str] = []
    if amount <= 0:
        return variants

    if amount >= 10_000 and amount % 10_000 == 0:
        man = amount // 10_000
        variants += [f"{man:,}만원", f"{man:,}만 원", f"{man}만원", f"{man}만 원"]
    elif amount >= 10_000:
        man = amount // 10_000
        rem = amount % 10_000
        variants += [f"{man:,}만 {rem:,}원", f"{man}만 {rem}원"]

    variants += [f"{amount:,}원", f"{amount}원"]
    return variants


# ═══════════════════════════════════════════════════════════════════════════
# G-CALC : 검증된 예시 결과값 정합성
# ═══════════════════════════════════════════════════════════════════════════

_SMALL_AMOUNT_THRESHOLD = 10_000  # 1만원 미만 소액(단순 요율값 등) 제외


def _pick_check_amounts(result: dict | int | float) -> list[tuple[str, int]]:
    """
    result에서 실제 검증할 금액 목록을 선별한다.
    - result dict에 'total' 키가 있으면 total만
    - result가 scalar면 그 값만
    - 그 외(복수 컴포넌트 dict)는 모든 양수 금액
    """
    if isinstance(result, (int, float)):
        if result >= _SMALL_AMOUNT_THRESHOLD:
            return [("result", int(result))]
        return []

    if isinstance(result, dict):
        # 'total' 키 우선
        if "total" in result:
            v = result["total"]
            if isinstance(v, (int, float)) and v >= _SMALL_AMOUNT_THRESHOLD:
                return [("total", int(v))]
            return []
        # 'total' 없으면 모든 양수 컴포넌트 (계산기 intent 등)
        return [
            (k, int(v))
            for k, v in result.items()
            if isinstance(v, (int, float)) and v >= _SMALL_AMOUNT_THRESHOLD
        ]
    return []


def check_g_calc(
    body_html: str,
    example_context: dict | None,
    intent: str | None = None,
) -> list[dict]:
    """
    example_context.examples[].result 의 검증된 금액이
    본문 텍스트에 하나 이상 등장하는지 확인한다.

    - documents intent: 절차 안내 글이므로 계산 결과 미인용 — 면제
    - total 필드 있으면 total만, 없으면 개별 컴포넌트 전체 검사

    Returns: gate fail dict 목록
    """
    if intent == "documents":
        return []  # 서류 안내 글은 계산 결과 인용 불필요

    fails: list[dict] = []
    examples = (example_context or {}).get("examples") or []
    if not examples:
        return fails

    text = _strip_html(body_html)

    for idx, ex in enumerate(examples):
        result = ex.get("result") or {}
        if not result:
            continue

        amounts = _pick_check_amounts(result)
        for field, amount in amounts:
            variants = _format_krw(amount)
            if not any(v in text for v in variants):
                fails.append({
                    "gate": "G-CALC",
                    "grade": "major",
                    "detail": (
                        f"예시 {idx + 1}번 '{field}' = {amount:,}원 -> "
                        f"본문에 미등장 (예상 표기: {variants[:2]})"
                    ),
                })
    return fails


# ═══════════════════════════════════════════════════════════════════════════
# G-NUMCON : 본문 내 산술식 모순 검사
# ═══════════════════════════════════════════════════════════════════════════

# "A만원 × B = C만원"  (B: 소수 0.X 또는 % 형식)
_ARITH2_RE = re.compile(
    r"([\d,]+)\s*만\s*원\s*[×x×]\s*([\d.]+)(?:%|\s*)\s*=\s*(?:약\s*)?([\d,]+)\s*만\s*원"
)
# "A만원 × B × C일 = D만원" (3항 곱셈 – 일수 포함)
_ARITH3_RE = re.compile(
    r"([\d,]+)\s*만\s*원\s*[×x×]\s*([\d.]+)\s*[×x×]\s*([\d,]+)\s*일\s*=\s*(?:약\s*)?([\d,]+)\s*만\s*원"
)

_ARITH_TOL = 0.015  # 1.5% 허용 오차 (반올림 차이 흡수)


def _check_mul(a_man: int, b: float, c_man_stated: int, label: str) -> dict | None:
    """a(만원) × b 의 예상값과 c_man_stated(만원)을 비교. 오차 초과 시 fail dict 반환."""
    if b > 1 and b < 100:  # % 표기 (e.g. "60" → 0.6)
        b /= 100
    expected = a_man * b
    if expected == 0:
        return None
    rel_err = abs(c_man_stated - expected) / expected
    if rel_err > _ARITH_TOL:
        return {
            "gate": "G-NUMCON",
            "grade": "major",
            "detail": (
                f"산술 오류 ({label}): {a_man}만원 × {b:.4g} "
                f"= {c_man_stated}만원 (계산값: {expected:,.1f}만원, 오차 {rel_err*100:.1f}%)"
            ),
        }
    return None


def check_g_numcon(body_html: str) -> list[dict]:
    """본문 내 명시적 산술식 정합성 검사."""
    fails: list[dict] = []
    text = _strip_html(body_html)

    # 3항 패턴 먼저
    for m in _ARITH3_RE.finditer(text):
        a = int(m.group(1).replace(",", ""))
        b = float(m.group(2))
        days = int(m.group(3).replace(",", ""))
        d_stated = int(m.group(4).replace(",", ""))
        if b > 1:
            b /= 100
        expected = a * b * days
        rel_err = abs(d_stated - expected) / max(expected, 1)
        if rel_err > _ARITH_TOL:
            fails.append({
                "gate": "G-NUMCON",
                "grade": "major",
                "detail": (
                    f"산술 오류: {m.group(1)}만원 × {m.group(2)} × {days}일 "
                    f"= {m.group(4)}만원 (계산값: {expected:,.0f}만원)"
                ),
            })

    # 2항 패턴
    for m in _ARITH2_RE.finditer(text):
        a = int(m.group(1).replace(",", ""))
        b = float(m.group(2))
        c = int(m.group(3).replace(",", ""))
        f = _check_mul(a, b, c, f"{m.group(1)}만원 × {m.group(2)}")
        if f:
            fails.append(f)

    return fails


# ═══════════════════════════════════════════════════════════════════════════
# G-LEGAL : 법적 근거 오인용 검사
# ═══════════════════════════════════════════════════════════════════════════

# slug → [(금지 키워드, 설명)]
_LEGAL_FORBIDDEN: dict[str, list[tuple[str, str]]] = {
    "severance-pay": [
        (
            "근로기준법 제36조",
            "퇴직금 지급기한은 근로자퇴직급여보장법 제9조 소관 (근기법 제36조는 임금 일반)",
        ),
        (
            "근로자퇴직급여 보장법 제8조",
            "지급기한 조항은 제9조 (제8조는 퇴직금 지급의무 규정)",
        ),
    ],
    "four-insurances": [
        (
            "부가가치세",
            "4대보험 취득신고와 무관한 부가가치세 언급",
        ),
    ],
}


def check_g_legal(body_html: str, slug: str | None) -> list[dict]:
    """법적 근거 오인용·무관 키워드 검출."""
    fails: list[dict] = []
    rules = _LEGAL_FORBIDDEN.get(slug or "", [])
    if not rules:
        return fails
    text = _strip_html(body_html)
    for keyword, reason in rules:
        if keyword in text:
            fails.append({
                "gate": "G-LEGAL",
                "grade": "major",
                "detail": f"오인용 키워드 '{keyword}' — {reason}",
            })
    return fails


# ═══════════════════════════════════════════════════════════════════════════
# G-STYLE+ : AI 문체 잔존 강화 검사
# ═══════════════════════════════════════════════════════════════════════════

_AI_STYLE_EXTRA = [
    "살펴보겠습니다",
    "알아보겠습니다",
    "살펴봅시다",
    "알아봅시다",
    "이해하셨을 것입니다",
    "이해할 수 있습니다",
    "생각해보면",
]


def check_g_style_plus(body_html: str) -> list[dict]:
    """G7 보완: 추가 AI 문체 패턴 검출."""
    fails: list[dict] = []
    text = _strip_html(body_html)
    hits = [p for p in _AI_STYLE_EXTRA if p in text]
    if hits:
        fails.append({
            "gate": "G-STYLE+",
            "grade": "minor",
            "detail": f"AI 문체 잔존 {len(hits)}건: {', '.join(hits)}",
        })
    return fails


# ═══════════════════════════════════════════════════════════════════════════
# 통합 실행 함수
# ═══════════════════════════════════════════════════════════════════════════

_ALL_GATES = {"G-CALC", "G-NUMCON", "G-LEGAL", "G-STYLE+"}


def run_integrity_gates(
    body_html: str,
    slug: str | None = None,
    example_context: dict | None = None,
    intent: str | None = None,
) -> tuple[list[str], list[dict]]:
    """
    모든 정합성 게이트 실행.
    Returns: (passed_gate_names, failed_gate_dicts)
    """
    all_failed: list[dict] = []
    all_failed.extend(check_g_numcon(body_html))
    all_failed.extend(check_g_calc(body_html, example_context, intent=intent))
    all_failed.extend(check_g_legal(body_html, slug))
    all_failed.extend(check_g_style_plus(body_html))

    failed_names = {f["gate"] for f in all_failed}
    passed = sorted(_ALL_GATES - failed_names)
    return passed, all_failed
