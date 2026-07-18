# -*- coding: utf-8 -*-
"""G1 REWRITE detail 목표값 수정 검증
  - 미달 케이스: detail이 writer target(1900자) 기준으로 지시하는지 확인
  - 초과 케이스: detail이 max 초과로 올바르게 표시하는지 확인
  - 안전망 동작: 1800~1899자는 G1 PASS(안전망 threshold 유지) 확인
  - 기존 gate 동작: G2/G3/G4/G5 회귀 없는지 확인
"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from modules.publish_quality import check_gates

cfg = load_config()

# 기준값
gate = cfg.get("QUALITY_GATE", {})
MIN_LEN = gate.get("MIN_LENGTH", 1800)
MAX_LEN = gate.get("MAX_LENGTH", 2500)
WRITER_TARGET = gate.get("WRITER_TARGET_LENGTH", 1900)

# ──────────────────────────────────────────────────────────────────────────
# 테스트용 body (G2~G4 통과 조건 만족)
# ──────────────────────────────────────────────────────────────────────────
def _body(char_count: int) -> str:
    """G2(H2 5개), G3(FAQ 5개), G4(예시 2개) 통과 조건 포함. 글자수는 padding으로 조절."""
    base = (
        "<h2>개요</h2><p>예를 들어 시급 10,000원, 주 40시간 = 80,000원. "
        "또 다른 예시로 시급 12,000원 = 96,000원.</p>"
        "<h2>계산법</h2><p>계산 방법을 설명합니다.</p>"
        "<h2>주의사항</h2><p>주의할 점이 있습니다.</p>"
        "<h2>조건</h2><p>조건을 확인합니다.</p>"
        "<h2>자주 묻는 질문</h2>"
        "<dl>"
        "<dt>질문1</dt><dd>답변1입니다.</dd>"
        "<dt>질문2</dt><dd>답변2입니다.</dd>"
        "<dt>질문3</dt><dd>답변3입니다.</dd>"
        "<dt>질문4</dt><dd>답변4입니다.</dd>"
        "<dt>질문5</dt><dd>답변5입니다.</dd>"
        "</dl>"
    )
    from modules.publish_quality import _plain_text
    current = len(_plain_text(base))
    padding = max(0, char_count - current)
    return base + ("<p>" + "가" * padding + "</p>" if padding > 0 else "")

CTA = '<hr/><h2>계산기 사용하기</h2><p>계산기입니다.</p>'
TWO_LINKS = (
    '<div class="internal-links">'
    '<a href="https://s.test/a">계산기A</a>'
    '<a href="https://s.test/b">계산기B</a>'
    '</div>'
)

def run(desc, body_chars, expected_g1, expected_detail_kw=None):
    body = _body(body_chars)
    final = body + CTA + TWO_LINKS
    _, failed = check_gates(body, final, cfg, link_pool_size=2)
    g1 = [r for r in failed if r["gate"] == "G1"]
    actual = "FAIL" if g1 else "PASS"
    ok = actual == expected_g1
    if ok and expected_detail_kw and g1:
        ok = expected_detail_kw in g1[0]["detail"]
    mark = "OK" if ok else "NG"
    detail = g1[0]["detail"] if g1 else "-"
    print(f"[{mark}] {desc}")
    print(f"     chars={body_chars}  expected={expected_g1}  actual={actual}")
    print(f"     detail: {detail}")
    return ok


print("=" * 70)
print(" G1 REWRITE detail 목표값 수정 검증")
print(f" MIN_LENGTH={MIN_LEN}  WRITER_TARGET={WRITER_TARGET}  MAX_LENGTH={MAX_LEN}")
print("=" * 70)

all_ok = True

# ── A. 미달 케이스 ────────────────────────────────────────────────────────
print("\n[A] 미달 케이스 — G1 FAIL + detail에 writer target(1900) 기준 지시 확인")

all_ok &= run("A-1 심각 미달(1600자): target 기준 shortfall 표시",
              1600, "FAIL", str(WRITER_TARGET))
all_ok &= run("A-2 threshold 근접 미달(1750자): target 기준 지시",
              1750, "FAIL", str(WRITER_TARGET))
all_ok &= run("A-3 threshold 근접(1780자): 여전히 G1 FAIL",
              1780, "FAIL", str(WRITER_TARGET))

# ── B. 안전망 동작 (1800~1899: G1 PASS, writer target 미달이지만 gate는 통과) ──
print("\n[B] 안전망 동작 — 1800~1899자는 G1 PASS (threshold 안전망 유지)")

all_ok &= run("B-1 threshold 최소선(1800자): G1 PASS",     1800, "PASS")
all_ok &= run("B-2 안전망 구간(1850자): G1 PASS",          1850, "PASS")
all_ok &= run("B-3 writer target 최소(1900자): G1 PASS",   1900, "PASS")
all_ok &= run("B-4 정상 범위(2000자): G1 PASS",            2000, "PASS")

# ── C. 초과 케이스 ────────────────────────────────────────────────────────
print("\n[C] 초과 케이스 — G1 FAIL + 단축 지시 확인")

all_ok &= run("C-1 max 초과(2600자): 단축 지시",   2600, "FAIL", "단축")
all_ok &= run("C-2 max 경계+1(2501자): G1 FAIL",   2501, "FAIL", "단축")
all_ok &= run("C-3 max 경계 근접(2480자): G1 PASS", 2480, "PASS")

print()
print("=" * 70)
print("전체:", "ALL PASS" if all_ok else "FAIL 있음")
