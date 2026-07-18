# -*- coding: utf-8 -*-
"""F1 실전 검증 — G1 REWRITE 목표 변경(1800→1900)이 LLM 행동을 실제로 바꾸는지 확인.

실행: python scripts/diag_g1_f1_validation.py
출력: 계산기별 시도 × Rewrite 단계별 글자수 + 수렴 위치 판정

목적:
- "문구 변경 성공"(단위 테스트)과 "LLM 행동 변화"를 분리 검증
- Rewrite 단계별 글자수 추이 → threshold 수렴 or writer target 수렴 판정
"""
import sys, json, time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from modules.calculator_pipeline import (
    _write_article, _load_legal_basis,
)
from modules.calculator_seo_generator import generate_seo
from modules.calculator_faq_generator import generate_faq
from modules.publish_quality import check_publish_quality, _plain_text
from modules.collector.calculator import CalculatorCollector
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

cfg = load_config()

# ── 대상 계산기 + 각 키워드 2건 ──────────────────────────────────────────────
TARGET_SLUGS_KEYWORDS = {
    "육아휴직_급여_계산기":    ["육아휴직 급여 계산", "육아휴직 급여 계산법"],
    "weekly-holiday-allowance": ["주휴수당 계산", "주휴수당 계산법"],
    "unemployment-benefit":     ["실업급여 계산", "실업급여 계산법"],
    "four-insurances":          ["4대보험 계산", "4대보험 계산법"],
}

# ── 실제 calc 오브젝트 조회 ───────────────────────────────────────────────────
print("계산기 데이터 로딩 중...")
repo = CalculatorRepository(get_db_adapter(cfg))
calcs_by_slug = {str(c.get("slug", "")): c for c in repo.get_all()}

# ── REWRITE 시뮬레이션 루프 ──────────────────────────────────────────────────
MAX_REWRITE = 3
gate_cfg = cfg.get("QUALITY_GATE", {})
MIN_LEN = gate_cfg.get("MIN_LENGTH", 1800)
WRITER_TARGET = gate_cfg.get("WRITER_TARGET_LENGTH", 1900)
MAX_LEN = gate_cfg.get("MAX_LENGTH", 2500)

print(f"설정: MIN_LENGTH={MIN_LEN}  WRITER_TARGET={WRITER_TARGET}  MAX_LENGTH={MAX_LEN}")
print()

# 결과 테이블 축적
all_rows = []

def run_sample(slug, keyword, calc):
    """한 (계산기, 키워드) 쌍에 대해 초기 생성 + 최대 3회 REWRITE 시뮬레이션."""
    row = {"slug": slug, "keyword": keyword, "steps": []}

    # SEO + FAQ
    try:
        seo = generate_seo(cfg, calc.get("name", keyword), keyword)
    except Exception as e:
        print(f"    [ERROR] generate_seo 실패: {e}")
        return None
    faq = []
    if calc.get("faq"):
        try:
            faq = json.loads(calc["faq"]) if isinstance(calc["faq"], str) else calc["faq"]
        except Exception:
            faq = []
    if not faq:
        try:
            faq = generate_faq(cfg, calc.get("name", keyword))
        except Exception as e:
            print(f"    [WARN] generate_faq 실패(빈 FAQ 사용): {e}")

    # 초기 생성
    try:
        body_html, _ = _write_article(cfg, calc, keyword, seo, faq)
    except Exception as e:
        print(f"    [ERROR] _write_article 실패: {e}")
        return None

    qc = check_publish_quality(cfg, body_html, body_html, calc, link_pool_size=2)
    plain_len = len(_plain_text(body_html))
    g1_result = "PASS" if not any(r["gate"] == "G1" for r in (qc.get("failed_rules") or [])) else "FAIL"
    row["steps"].append({"attempt": 0, "chars": plain_len, "g1": g1_result,
                         "qc_result": qc.get("result")})

    # REWRITE 루프
    failed_rules = qc.get("failed_rules") or []
    for attempt in range(1, MAX_REWRITE + 1):
        if qc.get("result") != "REWRITE":
            break
        # G1이 failed_rules에 없으면 다른 이유로 REWRITE — 그래도 계속 추적
        try:
            time.sleep(1)  # API rate limit 여유
            body_html, _ = _write_article(cfg, calc, keyword, seo, faq,
                                          failed_rules=failed_rules)
        except Exception as e:
            print(f"    [ERROR] REWRITE {attempt} _write_article 실패: {e}")
            break

        qc = check_publish_quality(cfg, body_html, body_html, calc, link_pool_size=2)
        plain_len = len(_plain_text(body_html))
        g1_result = "PASS" if not any(r["gate"] == "G1" for r in (qc.get("failed_rules") or [])) else "FAIL"
        row["steps"].append({"attempt": attempt, "chars": plain_len, "g1": g1_result,
                             "qc_result": qc.get("result")})
        failed_rules = qc.get("failed_rules") or []

    return row


def convergence_verdict(steps):
    """수렴 위치 판정."""
    chars = [s["chars"] for s in steps]
    final = chars[-1] if chars else 0
    if final >= WRITER_TARGET:
        return "SUCCESS (≥1900)"
    elif final >= MIN_LEN:
        return f"PARTIAL ({final}자, 안전망 통과but target 미달)"
    else:
        return f"FAIL ({final}자, threshold 미달)"


# ── 실행 ──────────────────────────────────────────────────────────────────────
print("=" * 72)
print(f" F1 실전 검증 — 4계산기 × 2키워드 = 총 8건")
print("=" * 72)

for slug, keywords in TARGET_SLUGS_KEYWORDS.items():
    calc = calcs_by_slug.get(slug)
    if not calc:
        print(f"\n[{slug}] 계산기 데이터 없음 — 건너뜀")
        continue

    print(f"\n{'─'*72}")
    print(f"  계산기: {calc.get('name','?')} ({slug})")
    print(f"{'─'*72}")

    for ki, keyword in enumerate(keywords, 1):
        print(f"\n  [{slug[:20]}] 시도 {ki}: keyword={keyword!r}")
        row = run_sample(slug, keyword, calc)
        if not row:
            print("    → 건너뜀 (생성 실패)")
            continue
        all_rows.append(row)

        for s in row["steps"]:
            tag = "(초기)" if s["attempt"] == 0 else f"(REWRITE {s['attempt']})"
            g1_mark = "✓" if s["g1"] == "PASS" else "✗"
            print(f"    {tag:12} {s['chars']:4}자  G1:{g1_mark}  qc={s['qc_result']}")

        verdict = convergence_verdict(row["steps"])
        print(f"    → 수렴 판정: {verdict}")


# ── 최종 요약 테이블 ──────────────────────────────────────────────────────────
print()
print("=" * 72)
print(" 최종 요약")
print("=" * 72)
print(f"{'계산기':<25} {'키워드':<18} {'초기':>5} {'RW1':>5} {'RW2':>5} {'RW3':>5} {'최종G1':>7} {'판정'}")
print("-" * 72)

success, partial, fail = 0, 0, 0
for row in all_rows:
    steps = row["steps"]
    chars_by_attempt = {s["attempt"]: s["chars"] for s in steps}
    final_g1 = steps[-1]["g1"] if steps else "?"
    verdict = convergence_verdict(steps)
    if "SUCCESS" in verdict:
        success += 1
    elif "PARTIAL" in verdict:
        partial += 1
    else:
        fail += 1
    print(f"{row['slug'][:25]:<25} {row['keyword'][:18]:<18} "
          f"{chars_by_attempt.get(0,'-'):>5} "
          f"{chars_by_attempt.get(1,'-'):>5} "
          f"{chars_by_attempt.get(2,'-'):>5} "
          f"{chars_by_attempt.get(3,'-'):>5} "
          f"  {'✓' if final_g1=='PASS' else '✗':>4}  {verdict[:30]}")

print()
print(f"성공(≥1900): {success}건  부분(1800~1899): {partial}건  실패(<1800): {fail}건  총:{len(all_rows)}건")
print()

# ── 판정 ─────────────────────────────────────────────────────────────────────
total = len(all_rows)
if total == 0:
    print("결과 없음")
elif success / total >= 0.7:
    print("판정: SUCCESS — F1 효과 확인. 대부분의 REWRITE가 1900자 이상으로 수렴.")
elif (success + partial) / total >= 0.7:
    print("판정: PARTIAL — 평균 글자수 증가 확인, 일부 계산기 1800~1899 반복. F2 검토 권장.")
else:
    print("판정: FAIL — 단순 목표 숫자 변경으로는 불충분. F2(섹션별 최소량) 검토 필요.")
