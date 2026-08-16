# -*- coding: utf-8 -*-
"""
Phase 5-E: 10개 아티클 자동 정합성 게이트 검증
G-CALC / G-NUMCON / G-LEGAL / G-STYLE+

결과: 각 게이트 PASS/FAIL + 세부 내용 출력
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from modules.content_integrity import run_integrity_gates

BASE = pathlib.Path(__file__).parent.parent
ARTICLES = BASE / "data" / "phase5-c" / "articles"
REQUESTS = BASE / "data" / "phase5-c" / "requests"


def load_request(stem: str) -> dict:
    num = stem.split("_")[0]
    for f in REQUESTS.glob(f"{num}_*.json"):
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def main():
    results = []

    for html_file in sorted(ARTICLES.glob("*.html")):
        if html_file.name in ("gallery.html", "regen_check.html"):
            continue
        body_html = html_file.read_text(encoding="utf-8")
        meta = load_request(html_file.stem)
        slug = meta.get("slug", "")
        intent = meta.get("intent", "")
        ex_ctx = meta.get("example_context") or {}

        passed, failed = run_integrity_gates(
            body_html, slug=slug, example_context=ex_ctx, intent=intent
        )

        results.append({
            "file": html_file.name,
            "slug": slug,
            "intent": intent,
            "passed": passed,
            "failed": failed,
        })

    # ── 출력 ────────────────────────────────────────────────────────────────
    sep = "-" * 110
    print(f"\n{'STATUS':<6}  {'파일명':<50}  {'실패 게이트'}")
    print(sep)

    total_fail = 0
    for r in results:
        gf = r["failed"]
        status = "PASS" if not gf else "FAIL"
        if gf:
            total_fail += 1
        gate_str = ", ".join(sorted({f["gate"] for f in gf})) if gf else "—"
        print(f"{status:<6}  {r['file']:<50}  {gate_str}")
        for f in gf:
            grade_tag = f"[{f['grade'].upper()}]"
            print(f"         {grade_tag:<9} {f['gate']}: {f['detail']}")

    print(sep)
    if total_fail == 0:
        print("RESULT: ALL 10 PASS -- 정합성 게이트 전원 통과")
    else:
        print(f"RESULT: {total_fail}/10 FAIL -- 위 항목 수정 필요")
    print()
    return total_fail


if __name__ == "__main__":
    sys.exit(main())
