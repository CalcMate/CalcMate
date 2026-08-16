# -*- coding: utf-8 -*-
"""
Phase 5-D: Phase 5-C 샘플 10개를 Phase 5-D 신규/변경 게이트로만 재검증.

Phase 5-D 변경 범위:
  G1: intent별 min_len (1750/1850/2000/1850)
  G4: documents OR not has_verified → 면제
  G8: documents → article 조항 번호 면제
  G-NEW2: calculator+has_verified=True → "= N원" × 2 필요

G2/G3/G5/G6/G7 등 **미변경** 게이트는 재검증 대상 아님.
(G5/G6는 final_html 기반 — body_html 파일에는 해당 없음)
"""
import json, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from modules.publish_quality import _plain_text, _check_g8

BASE = pathlib.Path(__file__).parent.parent
articles_dir = BASE / "data" / "phase5-c" / "articles"
requests_dir = BASE / "data" / "phase5-c" / "requests"

_G1_MIN_BY_INTENT = {
    "howto": 1750, "documents": 1850, "eligibility": 2000, "calculator": 1850,
}
_DEFAULT_MIN = 1800
_MAX_LEN = 2500
_GNEW2_RE = re.compile(r'(?:=\s*|약\s*)[\d,]+\s*(?:만|억|천)?\s*원')


def load_request_meta(stem: str) -> dict:
    num = stem.split("_")[0]
    for req_file in requests_dir.glob(f"{num}_*.json"):
        try:
            d = json.loads(req_file.read_text(encoding="utf-8"))
            return {
                "intent": d.get("intent"),
                "slug": d.get("calculator_slug") or d.get("slug", ""),
                "has_verified": bool(d.get("has_formula") or d.get("formula")),
            }
        except Exception:
            pass
    return {"intent": None, "slug": "", "has_verified": False}


results = []
for html_file in sorted(articles_dir.glob("*.html")):
    if html_file.name in ("gallery.html", "regen_check.html"):
        continue
    body_html = html_file.read_text(encoding="utf-8")
    meta = load_request_meta(html_file.stem)
    intent = meta["intent"]
    has_verified = meta["has_verified"]
    slug = meta["slug"]

    body_text = _plain_text(body_html)
    text_len = len(body_text)
    failed = []

    # ── G1: intent별 min_len ──────────────────────────────────────────
    min_len = _G1_MIN_BY_INTENT.get(intent, _DEFAULT_MIN)
    if text_len < min_len:
        failed.append({
            "gate": "G1",
            "detail": f"본문 {text_len}자 < 최소 {min_len}자 (intent={intent})"
        })
    elif text_len > _MAX_LEN:
        failed.append({
            "gate": "G1",
            "detail": f"본문 {text_len}자 > 최대 {_MAX_LEN}자"
        })

    # ── G4: calculator+has_verified → MIN_EXAMPLES=2 ─────────────────
    _g4_exempt = (intent == "documents") or (not has_verified)
    if not _g4_exempt:
        from modules.publish_quality import _count_examples
        ex = _count_examples(body_html)
        if ex < 2:
            failed.append({
                "gate": "G4",
                "detail": f"계산 예시 {ex}개 < 최소 2개 (intent={intent}, has_verified={has_verified})"
            })

    # ── G8: documents → article 면제 ─────────────────────────────────
    if slug:
        g8_fails = _check_g8(body_html, {"slug": slug}, intent=intent)
        failed.extend(g8_fails)

    # ── G-NEW2: calculator+has_verified → "= N원" × 2 ────────────────
    if (intent == "calculator") and has_verified:
        numeric = _GNEW2_RE.findall(body_text)
        if len(numeric) < 2:
            failed.append({
                "gate": "G-NEW2",
                "detail": f"'= 숫자원' {len(numeric)}개 < 최소 2개 (calculator+verified)"
            })

    results.append({
        "file": html_file.name,
        "slug": slug,
        "intent": intent,
        "has_verified": has_verified,
        "text_len": text_len,
        "gates_failed": [f["gate"] for f in failed],
        "failed_detail": [f["detail"] for f in failed],
    })

all_pass = True
print(f"{'STATUS':<6} | {'파일명':<45} | {'intent':<12} | {'len':>5} | 실패 게이트")
print("-" * 100)
for r in results:
    gf = r.get("gates_failed", [])
    status = "PASS" if not gf else "FAIL"
    if gf:
        all_pass = False
    fname = r["file"][:45]
    intent = r.get("intent", "?") or "?"
    tlen = r.get("text_len", 0)
    failed_str = ",".join(gf) if gf else "-"
    print(f"{status:<6} | {fname:<45} | {intent:<12} | {tlen:>5} | {failed_str}")
    for det in r.get("failed_detail", []):
        print(f"{'':6}   detail: {det}")

print()
print("=" * 100)
if all_pass:
    print("RESULT: ALL PASS -- Phase 5-C 10개 샘플 × Phase 5-D 변경 게이트 전원 통과")
else:
    fail_cnt = sum(1 for r in results if r.get("gates_failed"))
    print(f"RESULT: {fail_cnt} FAIL(s) -- 위 항목 확인 필요")
sys.exit(0 if all_pass else 1)
