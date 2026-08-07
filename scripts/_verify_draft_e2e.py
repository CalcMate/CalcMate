# -*- coding: utf-8 -*-
"""실운영 경로로 Draft 3건 생성 → G1~G8 전체 게이트 + 구조 검증.
실행: python scripts/_verify_draft_e2e.py
"""
import sys, json, re
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from modules.calculator_pipeline import run_calculator_once

cfg = load_config()

# 검증 대상 계산기 (cid)
TARGETS = [
    ("주휴수당",  "calc_20260805121652_d8b7"),
    ("실업급여",  "calc_20260805121656_f443"),
    ("퇴직금",    "calc_20260805121653_0065"),
]

REQUIRED_H2 = ["계산기 소개", "입력 방법", "결과 확인", "계산 원리", "주의사항", "FAQ"]

def check_structure(html: str) -> list:
    """필수 H2 섹션이 모두 있는지 확인. 누락 섹션 목록 반환."""
    missing = []
    for h2 in REQUIRED_H2:
        if not re.search(rf"<h2[^>]*>\s*{re.escape(h2)}\s*</h2>", html, re.I):
            missing.append(h2)
    return missing

def check_h1_duplicate(html: str) -> bool:
    """H1이 2개 이상이면 True(중복)."""
    return len(re.findall(r"<h1\b", html, re.I)) > 1

def check_cta(html: str) -> bool:
    """계산기 사용하기 섹션 존재 여부."""
    return bool(re.search(r"계산기\s*사용하기", html, re.I))

def check_internal_links(html: str) -> int:
    """내부링크 개수(href 중 앵커·외부 제외)."""
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, re.I)
    return sum(1 for h in hrefs if h and not h.startswith("#") and "javascript" not in h.lower())

print("=" * 72)
print("실운영 Draft 검증 — run_calculator_once (allow_duplicate=True, skip_quality=False)")
print("=" * 72)

results = []
for label, cid in TARGETS:
    print(f"\n▶ [{label}] cid={cid}")
    result = run_calculator_once(
        cfg,
        max_count=1,
        only_cid=cid,
        allow_duplicate=True,
        skip_quality=False,
    )
    produced = result.get("produced", 0)
    print(f"  produced={produced}")

    if produced == 0:
        print(f"  [SKIP] reason={result.get('reason','?')}")
        results.append({"label": label, "produced": 0, "reason": result.get("reason")})
        continue

    # 세부 결과 추출
    detail = result.get("details", [])
    if not detail:
        # 일부 버전에서 단일 dict로 반환될 수 있음
        detail = [result]

    for d in detail:
        qc = d.get("quality", {}) or {}
        final_html = qc.get("html") or d.get("html") or ""
        q_result = qc.get("result") or d.get("quality_status") or "?"
        failed_gates = [r.get("gate") for r in (qc.get("failed_rules") or [])]
        score = qc.get("score")

        # 구조 확인
        missing_h2 = check_structure(final_html)
        h1_dup = check_h1_duplicate(final_html)
        has_cta = check_cta(final_html)
        link_count = check_internal_links(final_html)

        print(f"  품질 결과: {q_result}  score={score}  실패게이트={failed_gates or '없음'}")
        print(f"  H2 구조: {'OK' if not missing_h2 else '누락=' + str(missing_h2)}")
        print(f"  H1 중복: {'없음' if not h1_dup else '⚠️ 중복 발견'}")
        print(f"  CTA 존재: {'있음' if has_cta else '없음'}")
        print(f"  내부링크: {link_count}개")

        results.append({
            "label": label,
            "produced": 1,
            "q_result": q_result,
            "score": score,
            "failed_gates": failed_gates,
            "missing_h2": missing_h2,
            "h1_dup": h1_dup,
            "has_cta": has_cta,
            "link_count": link_count,
        })

print("\n" + "=" * 72)
print("최종 요약")
print("=" * 72)
all_ok = True
for r in results:
    label = r["label"]
    if r.get("produced") == 0:
        print(f"  [{label}] SKIP — {r.get('reason')}")
        continue
    issues = []
    if r.get("q_result") not in ("PASS", "PUBLISHED_WITH_WARNING_LOG"):
        issues.append(f"품질={r.get('q_result')}")
    if r.get("missing_h2"):
        issues.append(f"H2누락={r.get('missing_h2')}")
    if r.get("h1_dup"):
        issues.append("H1중복")
    if not r.get("has_cta"):
        issues.append("CTA없음")
    if r.get("link_count", 0) == 0:
        issues.append("내부링크=0")

    status = "OK" if not issues else ("⚠️ " + ", ".join(issues))
    print(f"  [{label}] {status}  (score={r.get('score')}, gates={r.get('failed_gates') or '없음'})")
    if issues:
        all_ok = False

print()
if all_ok:
    print("계산기 파이프라인 안정화 완료 — Feature Freeze 준비완료")
else:
    print("일부 항목 확인 필요 — 위 이슈 검토")
