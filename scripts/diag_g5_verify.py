# -*- coding: utf-8 -*-
"""Adaptive G5 단위 검증 (AI 호출 없음)"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")

from modules.publish_quality import check_gates

BODY_OK = """
<h2>주휴수당이란</h2><p>주휴수당은 일주일에 15시간 이상 근무한 근로자에게 지급됩니다. 예를 들어 시급 10,000원이면 주휴수당은 80,000원 = 10,000원 × 8시간입니다. 또 다른 예시로 시급 12,000원이면 96,000원 × 1 = 96,000원입니다.</p>
<h2>주휴수당 계산법</h2><p>주휴수당 계산 공식: 시급 × (주당 근로시간 ÷ 40 × 8). 예를 들어 주 40시간 기준 시급 10,000원이면 80,000원입니다. 계산해 보면 10,000원 × 8 = 80,000원입니다.</p>
<h2>주휴수당 지급 조건</h2><p>주 15시간 이상, 소정근로일 개근 시 지급됩니다.</p>
<h2>주휴수당 계산 예시</h2><p>예를 들어 주 40시간 근무, 시급 10,000원이면 주휴수당 = 10,000원 × 8 = 80,000원입니다. 또 다른 조건으로 주 30시간 근무, 시급 12,000원이면 = 12,000원 × 6 = 72,000원입니다.</p>
<h2>자주 묻는 질문</h2>
<dl>
  <dt>주 15시간 미만이면?</dt><dd>주휴수당이 발생하지 않습니다.</dd>
  <dt>일용직도 받을 수 있나요?</dt><dd>소정 요건 충족 시 가능합니다.</dd>
  <dt>아르바이트도 해당되나요?</dt><dd>네, 근로기준법상 근로자라면 해당됩니다.</dd>
  <dt>결근하면 어떻게 되나요?</dt><dd>소정근로일에 결근하면 주휴수당이 발생하지 않습니다.</dd>
  <dt>주 40시간이 넘으면?</dt><dd>초과시간은 연장근로수당이 따로 적용됩니다.</dd>
</dl>
<h2>관련 법령</h2><p>근로기준법 제55조에 따라 사용자는 근로자에게 1주에 평균 1회 이상의 유급휴일을 보장해야 합니다.</p>
""" * 2

CTA = '<hr/><h2>계산기 사용하기</h2><p>아래 SalaryMate 계산기를 이용하면 자동으로 계산할 수 있습니다.</p>'
ONE_LINK = (
    '<div class="internal-links">'
    '<a href="https://salarymate.example/a">관련 계산기 A</a>'
    '</div>'
)
TWO_LINKS = (
    '<div class="internal-links">'
    '<a href="https://salarymate.example/a">관련 계산기 A</a>'
    '<a href="https://salarymate.example/b">관련 계산기 B</a>'
    '</div>'
)

cfg = {"QUALITY_GATE": {"MIN_LENGTH": 1800, "MAX_LENGTH": 2500, "MIN_H2": 5, "MAX_H2": 7,
                         "MIN_FAQ": 5, "MIN_EXAMPLES": 2, "MIN_INTERNAL_LINKS": 2, "CTA_COUNT": 1}}

CASES = [
    # (desc, final_html, link_pool_size, expected_g5)
    ("Cold Start: pool=0, links=0",         BODY_OK + CTA,            0, "PASS"),
    ("1건 쌓임: pool=1, links=1",            BODY_OK + CTA + ONE_LINK, 1, "PASS"),
    ("inject 버그: pool=1, links=0",         BODY_OK + CTA,            1, "FAIL"),
    ("정상: pool=5, links=2",                BODY_OK + CTA + TWO_LINKS, 5, "PASS"),
    ("inject 버그: pool=5, links=1",         BODY_OK + CTA + ONE_LINK, 5, "FAIL"),
    ("dead link + pool=0",                  BODY_OK + '<a href="#">#</a>' + CTA, 0, "FAIL"),
]

print("=" * 65)
all_pass = True
for desc, final_html, pool, expected in CASES:
    _, failed = check_gates(BODY_OK, final_html, cfg, link_pool_size=pool)
    g5_fail = [r for r in failed if r.get("gate") == "G5"]
    actual = "FAIL" if g5_fail else "PASS"
    ok = actual == expected
    all_pass = all_pass and ok
    mark = "OK" if ok else "NG"
    detail = g5_fail[0].get("detail", "") if g5_fail else ""
    print(f"[{mark}] {desc}")
    print(f"     pool={pool}  expected={expected}  actual={actual}  detail={detail!r}")

print("=" * 65)
print("전체:", "ALL PASS" if all_pass else "FAIL 있음")
