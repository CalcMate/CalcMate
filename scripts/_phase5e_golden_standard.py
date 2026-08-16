# -*- coding: utf-8 -*-
"""
Phase 5-E STEP 3 — Golden Standard 최종 판정
WP published 본문 + 로컬 gate 검증 결합
"""
from __future__ import annotations
import sys, json, re
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import requests as req
from modules.publish_quality import _plain_text
from modules.content_integrity import run_integrity_gates
from modules.law_ssot import get_forbidden_in_content

WP_BASE = "http://127.0.0.1"
WP_HOST = "salarymate.test"
WP_AUTH = ("geminia", "IfSt cfZ4 CVT5 sqTi DFdj bx4j")

ARTS_DIR = BASE / "data" / "phase5-c" / "articles"
REQS_DIR = BASE / "data" / "phase5-c" / "requests"

ARTICLE_MAP = [
    ("01", "severance-pay",           "퇴직금 받는 조건",      313, "eligibility"),
    ("02", "weekly-holiday-allowance","주휴수당 계산법",        316, "howto"),
    ("03", "unemployment-benefit",    "실업급여 조건",          319, "eligibility"),
    ("04", "four-insurances",         "4대보험 계산",           322, "calculator"),
    ("05", "annual-leave-allowance",  "연차수당 계산방법",      325, "howto"),
    ("06", "severance-pay",           "퇴직금 신청서류",        328, "documents"),
    ("07", "육아휴직_급여_계산기",      "육아휴직 급여 조건",    329, "eligibility"),
    ("08", "연말정산_환급액_계산기",     "연말정산 환급액",       330, "calculator"),
    ("09", "unemployment-benefit",    "실업급여 신청방법",      333, "howto"),
    ("10", "four-insurances",         "4대보험 취득신고 서류",  336, "documents"),
]

REGEN = {"04", "05", "07", "10"}

FORBIDDEN_MAP = {
    "four-insurances": ["3.52%", "3.535%", "3.53%", "12.95%", "12.81%", "12.27%", "7일 이내", "10일 이내"],
    "육아휴직_급여_계산기": ["상한 150만원", "상한액 150만원", "최대 150만원", "상한 120만원", "상한액 120만원", "최대 120만원"],
}

MIN_LEN = {"eligibility": 2000, "howto": 1750, "documents": 1850, "calculator": 1850}
SEP = "=" * 70


def wp_get_post(post_id: int, session: req.Session) -> dict:
    r = session.get(f"{WP_BASE}/wp-json/wp/v2/posts/{post_id}", timeout=10)
    r.raise_for_status()
    return r.json()


def extract_cta_link(html: str) -> str:
    m = re.search(r'<a\s+href=["\']([^"\']*calcmate\.kr[^"\']*)["\']', html)
    return m.group(1) if m else ""


def verdict(results: list[dict]) -> str:
    for r in results:
        if r.get("overall") == "FAIL":
            return "FAIL"
    if any(r.get("overall") == "WARN" for r in results):
        return "WARN"
    return "PASS"


def main():
    session = req.Session()
    session.auth = WP_AUTH
    session.headers["Host"] = WP_HOST

    print(SEP)
    print("Phase 5-E Golden Standard 최종 판정")
    print(f"시각: {datetime.now().isoformat()}")
    print(SEP)

    all_results = []

    for prefix, slug, keyword, post_id, intent in ARTICLE_MAP:
        print(f"\n[{prefix}] {keyword}")

        # WP에서 published 본문 취득
        try:
            post = wp_get_post(post_id, session)
        except Exception as e:
            print(f"  WP 조회 실패: {e}")
            all_results.append({"prefix": prefix, "overall": "FAIL", "reason": str(e)})
            continue

        wp_html = post.get("content", {}).get("rendered", "")
        wp_txt  = _plain_text(wp_html)
        cats    = post.get("categories", [])
        tags    = post.get("tags", [])
        url     = post.get("link", "")

        # 로컬 HTML (gate 검증용)
        local_files = sorted(ARTS_DIR.glob(f"{prefix}_*.html"))
        local_html  = local_files[0].read_text(encoding="utf-8") if local_files else ""

        issues = []
        warns  = []

        # ── A. CTA/링크 확인 (WP published 본문 기준)
        has_cta      = "<h2>계산기 사용하기</h2>" in wp_html
        cta_url      = extract_cta_link(wp_html)
        has_internal = 'class="internal-links"' in wp_html
        a_ok = has_cta and bool(cta_url) and has_internal
        print(f"  A.CTA     : {'✅' if has_cta else '❌'} | calcmate링크={'✅ ' + cta_url if cta_url else '❌'}")
        print(f"            내부링크={'✅' if has_internal else '❌'}")
        if not a_ok:
            issues.append("CTA/링크 미삽입")

        # ── B. 카테고리/태그
        cat_ok = len(cats) >= 1 and cats != [1]  # 1=Uncategorized
        tag_ok = len(tags) >= 1
        print(f"  B.Category: {'✅' if cat_ok else '❌'} cats={cats} | tags={'✅' if tag_ok else '❌'} {tags[:3]}")
        if not cat_ok:
            issues.append(f"카테고리 미지정(cats={cats})")
        if not tag_ok:
            warns.append("태그 없음")

        # ── C. 법적 수치 (금지값 — 로컬 HTML 기준)
        forbidden = FORBIDDEN_MAP.get(slug, [])
        found_forbidden = [v for v in forbidden if v in wp_txt]
        if found_forbidden:
            print(f"  C.법정수치 : ❌ 금지값 발견: {found_forbidden}")
            issues.append(f"금지값 잔존: {found_forbidden}")
        else:
            print(f"  C.법정수치 : ✅ 금지값 없음")

        # ── D. content_integrity gates (로컬 HTML)
        if local_html:
            passed, failed = run_integrity_gates(local_html, slug=slug, intent=intent)
            critical = [f for f in failed if f["grade"] == "critical"]
            major    = [f for f in failed if f["grade"] == "major"]
            minor    = [f for f in failed if f["grade"] == "minor"]
            gate_ok  = len(critical) == 0 and len(major) == 0
            print(f"  D.Gate    : {'✅' if gate_ok else '❌'} passed={len(passed)}/7  "
                  f"critical={len(critical)} major={len(major)} minor={len(minor)}")
            if critical:
                for f in critical:
                    print(f"            🔴 {f['gate']}: {f['detail'][:70]}")
                    issues.append(f"critical: {f['gate']}")
            if major:
                for f in major:
                    print(f"            🟡 {f['gate']}: {f['detail'][:70]}")
                    issues.append(f"major: {f['gate']}")
            if minor:
                for f in minor:
                    print(f"            ⚪ {f['gate']}: {f['detail'][:60]}")
                    warns.append(f"minor: {f['gate']}")
        else:
            print(f"  D.Gate    : ⚠️  로컬 HTML 없음")
            warns.append("로컬 HTML 없음")

        # ── E. 분량 (로컬 텍스트 기준)
        local_txt = _plain_text(local_html) if local_html else ""
        min_len   = MIN_LEN.get(intent, 1900)
        len_diff  = len(local_txt) - min_len
        if len_diff < 0:
            print(f"  E.분량    : ⚠️  {len(local_txt)}자 < {min_len}자({intent}) {len_diff}자 부족")
            warns.append(f"G1분량부족{len_diff}자")
        else:
            print(f"  E.분량    : ✅ {len(local_txt)}자 ≥ {min_len}자")

        # ── F. H2 구조
        h2s = re.findall(r'<h2[^>]*>\s*(.+?)\s*</h2>', local_html, re.I) if local_html else []
        has_faq = any("FAQ" in h for h in h2s)
        print(f"  F.H2      : {'✅' if has_faq else '❌'} {h2s}")
        if not has_faq:
            issues.append("FAQ H2 없음")

        # ── G. 이미지 (WP featured_media)
        featured = post.get("featured_media", 0)
        print(f"  G.이미지  : {'✅ featured_media=' + str(featured) if featured else '⚠️ featured_media 없음'}")
        if not featured:
            warns.append("featured_media 없음")

        # 종합 판정
        if issues:
            overall = "FAIL"
        elif warns:
            overall = "WARN"
        else:
            overall = "PASS"

        print(f"  판정      : {overall} | URL: {url}")
        all_results.append({
            "prefix": prefix, "keyword": keyword, "overall": overall,
            "issues": issues, "warns": warns, "url": url,
            "cat_ok": cat_ok, "tag_ok": tag_ok,
        })

    # ── 최종 종합 판정
    print(f"\n{SEP}")
    print("Golden Standard 최종 판정")
    print(SEP)
    print(f"\n{'번':>3} {'판정':<6} {'키워드':<20} 세부")
    print("-" * 70)
    for r in all_results:
        icon = "✅" if r["overall"] == "PASS" else ("⚠️" if r["overall"] == "WARN" else "❌")
        issues_str = " / ".join(r.get("issues", [])) or "—"
        warns_str  = " / ".join(r.get("warns", []))  or "—"
        print(f"[{r['prefix']}] {icon} {r['overall']:<5} {r['keyword']:<20}")
        if r.get("issues"):
            print(f"     FAIL 원인: {issues_str}")
        if r.get("warns"):
            print(f"     WARN: {warns_str}")

    final = verdict(all_results)
    pass_cnt = sum(1 for r in all_results if r["overall"] == "PASS")
    warn_cnt = sum(1 for r in all_results if r["overall"] == "WARN")
    fail_cnt = sum(1 for r in all_results if r["overall"] == "FAIL")

    print(f"\n{'─'*70}")
    print(f"PASS={pass_cnt} / WARN={warn_cnt} / FAIL={fail_cnt}")
    print(f"\n{'★'*3} Golden Standard 최종 판정: {final} {'★'*3}")
    if final == "PASS":
        print("→ 10개 Golden Standard 확정. 신규 5개 생성 단계 진행 가능.")
    elif final == "WARN":
        print("→ WARN 수준 이슈 존재. 발행은 유지하나 후속 개선 필요.")
        print("  WARN 항목은 Golden Standard 기준 내 허용 범위.")
        print("→ 10개 Golden Standard 잠정 확정. 신규 5개 생성 단계 진행 가능.")
    else:
        print("→ FAIL 항목 존재. 해당 건 원인 수정 후 재검수 필요.")

    # 결과 저장
    log_path = BASE / "logs" / "content_pipeline" / f"phase5e_golden_standard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    log_path.write_text(
        json.dumps({"ran_at": datetime.now().isoformat(), "final": final, "results": all_results},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n판정 로그: {log_path.name}")


if __name__ == "__main__":
    main()
