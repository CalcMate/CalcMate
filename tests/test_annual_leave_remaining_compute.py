# -*- coding: utf-8 -*-
"""tests/test_annual_leave_remaining_compute.py — annual-leave-remaining 계산 정확성 테스트.

STEP 15-C에서 발견된 회귀(1년 미만 구간에서 15일을 반환하던 문제)를 다시 잡기 위한
전용 테스트. modules.app_generator._compute_js()가 실제로 생성하는 JS를 Node.js로
직접 실행해 검증한다(DB row와 무관 — mock calc dict만 사용, DB 읽기/쓰기 없음).

근로기준법 제60조 제1항(1년 미만, 매월 개근 시 1일, 최대 11일) +
제4항(3년 이상 계속근로 시 2년마다 1일 가산, 25일 상한) 기준.

⚠️ STEP 15-E-R 시점 기준: 이 테스트는 계산 엔진(_compute_js 분기) 자체만 검증한다.
실제 DB calculators.input_schema는 아직 years_of_service 기준이라 화면 폼과
이 계산 엔진(months_of_service 기준)이 아직 연결되지 않은 상태다(별도 DB 갱신 필요).
"""
import json
import os
import subprocess
import tempfile

import pytest

from modules.app_generator import _compute_js

pytestmark = pytest.mark.skipif(
    subprocess.run(["node", "--version"], capture_output=True).returncode != 0,
    reason="Node.js 미설치 환경에서는 스킵",
)


def _run(months_of_service: int, used_days: int = 0) -> dict:
    js = _compute_js({"slug": "annual-leave-remaining"})
    harness = (
        "globalThis.window = globalThis;\n" + js + "\n"
        + "var out = window.computeResult("
        + json.dumps({"months_of_service": months_of_service, "used_days": used_days},
                     ensure_ascii=False)
        + ");\n"
        + "process.stdout.write(JSON.stringify(out));\n"
    )
    fd, path = tempfile.mkstemp(suffix=".js")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(harness)
        r = subprocess.run(["node", path], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=10)
    finally:
        os.unlink(path)
    if r.returncode != 0:
        raise RuntimeError(f"node 실행 실패: {r.stderr}")
    return json.loads(r.stdout)


@pytest.mark.parametrize("months,expected", [
    (0, 0),
    (1, 1),
    (6, 6),
    (11, 11),
    (12, 15),
    (13, 15),
    (23, 15),
    (24, 15),
    (36, 16),
    (60, 17),
    (252, 25),
    (300, 25),
])
def test_total_days_boundary_values(months, expected):
    out = _run(months)
    assert out["total_days"] == expected, (
        f"months_of_service={months} → total_days={out['total_days']}, 기대값={expected}"
    )


def test_zero_months_does_not_regress_to_15():
    """STEP 15-C에서 발견된 정확한 회귀 재현 방지: 0개월 입력이 15일을 반환하면 실패."""
    out = _run(0)
    assert out["total_days"] != 15, "0개월 입력이 15일을 반환함 — STEP 15-C 회귀 재발"
    assert out["total_days"] == 0


def test_remaining_days_subtracts_used_days():
    out = _run(24, used_days=5)
    assert out["total_days"] == 15
    assert out["remaining_days"] == 10


def test_negative_months_returns_null():
    assert _run(-1) is None


def test_negative_used_days_returns_null():
    assert _run(12, used_days=-1) is None


def test_25_day_cap_holds_beyond_21_years():
    out_21y = _run(252)
    out_30y = _run(360)
    assert out_21y["total_days"] == 25
    assert out_30y["total_days"] == 25


@pytest.mark.parametrize("months", [1, 6, 11])
def test_formula_cites_article_2_under_12_months(months):
    """STEP 15-L에서 발견된 회귀 재현 방지: 1년 미만 구간의 _formula(화면 노출 문구)는
    근로기준법 제60조 제2항을 인용해야 하며, 제1항을 인용하면 안 된다."""
    out = _run(months)
    assert "제60조 제2항" in out["_formula"], out["_formula"]
    assert "제60조 제1항" not in out["_formula"], out["_formula"]


@pytest.mark.parametrize("months", [12, 24, 36])
def test_formula_cites_article_1_at_12_months_and_above(months):
    """1년 이상 구간의 _formula는 근로기준법 제60조 제1항(및 제4항)을 인용해야 한다."""
    out = _run(months)
    assert "제60조 제1항" in out["_formula"], out["_formula"]
