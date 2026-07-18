# -*- coding: utf-8 -*-
"""G4 연말정산 원인 조사 — 실제 writer 출력 2건 생성 후 전체 체인 비교"""
import sys, json, re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from modules import calculator_pipeline as CP
from modules.publish_quality import _count_examples, _plain_text, check_gates

cfg = load_config()

CALC = {
    "slug": "연말정산_환급액_계산기",
    "id": "calc_20260704111358_9168",
    "name": "연말정산 환급액 계산기",
    "formula": "결정세액 − 기납부세액(원천징수) = 환급 또는 추가납부",
}
SEO = {
    "seo_title": "연말정산 환급액 계산법 완벽 정리",
    "seo_description": "연말정산 환급액 계산법을 기준과 예시로 쉽게 설명합니다.",
}
FAQ = [
    {"question": "누가 환급 받을 수 있나요?", "answer": "근로소득이 있는 경우 해당됩니다."},
    {"question": "언제 신청하나요?", "answer": "다음 해 2월 정산합니다."},
]
# G4 카운터 패턴 그대로 재현
MARKER_RE = re.compile(r"예를\s*들어|예시로|가정하(?:면|여|고)|계산해\s*보면")
NUMERIC_RE = re.compile(r"=\s*[\d,]+\s*원|[\d,]+\s*원\s*[×xX*]")

KEYWORDS = ["연말정산 환급액 계산법", "연말정산 환급액 계산기 사용법"]

for run_num, keyword in enumerate(KEYWORDS, 1):
    print("=" * 70)
    print(f"=== 케이스 {run_num}: keyword={keyword!r} ===")
    print("=" * 70)

    try:
        body, tok = CP._write_article(cfg, CALC, keyword, SEO, FAQ)
    except Exception as e:
        print(f"  writer 오류: {e}")
        continue

    text = _plain_text(body)
    markers = MARKER_RE.findall(text)
    numerics = NUMERIC_RE.findall(text)
    ex_count = len(markers) + len(numerics)

    print(f"\n[G4 카운터 분해]")
    print(f"  marker 패턴 매치: {len(markers)}건 → {markers}")
    print(f"  numeric 패턴 매치: {len(numerics)}건 → {numerics[:10]}")
    print(f"  합계(G4 count): {ex_count}건  (MIN_EXAMPLES=2)")
    print(f"  G4 결과: {'PASS' if ex_count >= 2 else 'FAIL'}")

    # 계산 예시 주변 문맥 추출
    print(f"\n[계산 예시 문맥 — '예를 들어' 등장 위치 ±200자]")
    for m in re.finditer(r"예를\s*들어|예시로|가정하(?:면|여|고)|계산해\s*보면", text):
        start = max(0, m.start() - 50)
        end = min(len(text), m.end() + 200)
        snippet = text[start:end].replace("\n", " ")
        print(f"  [{m.group()}] ...{snippet}...")

    # 수식 결과 형식 — "원" 앞 패턴 분석 (만원/억원 포함)
    print(f"\n[본문 내 '원' 앞 수치 패턴 — 만원/억원 포함 전수]")
    won_contexts = re.findall(r"[\d,]+\s*(?:만|억)?\s*원", text)
    print(f"  전체 '원' 패턴: {won_contexts[:20]}")
    manwon = [w for w in won_contexts if "만" in w or "억" in w]
    print(f"  만원/억원 형식: {manwon[:15]}")
    rawwon = [w for w in won_contexts if "만" not in w and "억" not in w]
    print(f"  순수 숫자+원: {rawwon[:15]}")

    # check_gates 실행 (G5는 pool 없으니 0, G4만 봄)
    FINAL_HTML = body + (
        '<div class="internal-links">'
        '<a href="https://s.test/a">계산기A</a>'
        '<a href="https://s.test/b">계산기B</a>'
        '</div>'
        '<hr/><h2>계산기 사용하기</h2><p>계산기입니다.</p>'
    )
    _, failed = check_gates(body, FINAL_HTML, cfg, link_pool_size=2)
    g4 = [r for r in failed if r.get("gate") == "G4"]
    all_gates = [(r.get("gate"), r.get("detail")) for r in failed]
    print(f"\n[check_gates 결과]")
    print(f"  failed gates: {all_gates}")
    print(f"  G4: {'FAIL — ' + g4[0].get('detail','') if g4 else 'PASS'}")

    # 본문 앞 500자 — 구조 확인
    print(f"\n[본문 가시텍스트 첫 500자]")
    print(f"  {text[:500]}")
    print()
