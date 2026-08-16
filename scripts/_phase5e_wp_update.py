# -*- coding: utf-8 -*-
"""
scripts/_phase5e_wp_update.py — Phase 5-E STEP 3: 10개 WP 업데이트

목적:
  - PUT으로 기존 게시물 갱신 (새 HTML + CTA/링크 + 카테고리/태그)
  - 04/05/07/10: Phase 5-E 재생성 HTML 적용
  - 01/02/03/06/08/09: 기존 HTML 유지 + CTA/링크/카테고리만 후처리
  - 37개 기존 콘텐츠 미수정
"""
from __future__ import annotations
import sys, json, re
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import yaml
import requests as req
from modules.cta_builder import inject_cta_and_links
from modules.law_ssot import get_calc_name

WP_BASE  = "http://127.0.0.1"
WP_HOST  = "salarymate.test"
WP_AUTH  = ("geminia", "IfSt cfZ4 CVT5 sqTi DFdj bx4j")

ARTS_DIR = BASE / "data" / "phase5-c" / "articles"
REQS_DIR = BASE / "data" / "phase5-c" / "requests"
CAT_YAML = BASE / "config" / "calculator_categories.yaml"

ARTICLE_MAP = [
    ("01", "severance-pay",           "퇴직금 받는 조건",      313),
    ("02", "weekly-holiday-allowance","주휴수당 계산법",        316),
    ("03", "unemployment-benefit",    "실업급여 조건",          319),
    ("04", "four-insurances",         "4대보험 계산",           322),
    ("05", "annual-leave-allowance",  "연차수당 계산방법",      325),
    ("06", "severance-pay",           "퇴직금 신청서류",        328),
    ("07", "육아휴직_급여_계산기",      "육아휴직 급여 조건",    329),
    ("08", "연말정산_환급액_계산기",     "연말정산 환급액",       330),
    ("09", "unemployment-benefit",    "실업급여 신청방법",      333),
    ("10", "four-insurances",         "4대보험 취득신고 서류",  336),
]

REGEN_PREFIXES = {"04", "05", "07", "10"}  # STEP 1에서 재생성된 것


def _session() -> req.Session:
    s = req.Session()
    s.auth = WP_AUTH
    s.headers["Host"] = WP_HOST
    return s


SESSION = _session()
_CAT_MAP = yaml.safe_load(CAT_YAML.read_text(encoding="utf-8")) or {}


def _resolve_wp_category_ids(names: list[str]) -> list[int]:
    ids = []
    for name in names:
        r = SESSION.get(
            f"{WP_BASE}/wp-json/wp/v2/categories",
            params={"search": name, "per_page": 5}, timeout=10,
        )
        results = r.json()
        match = next((x for x in results if x.get("name") == name), None)
        if match:
            ids.append(match["id"])
        else:
            r2 = SESSION.post(
                f"{WP_BASE}/wp-json/wp/v2/categories",
                json={"name": name}, timeout=10,
            )
            if r2.ok:
                ids.append(r2.json()["id"])
                print(f"     [카테고리 신규생성] {name!r} → ID={ids[-1]}")
    return ids


def _resolve_wp_tag_ids(names: list[str]) -> list[int]:
    ids = []
    for name in names:
        r = SESSION.get(
            f"{WP_BASE}/wp-json/wp/v2/tags",
            params={"search": name, "per_page": 5}, timeout=10,
        )
        results = r.json()
        match = next((x for x in results if x.get("name") == name), None)
        if match:
            ids.append(match["id"])
        else:
            r2 = SESSION.post(
                f"{WP_BASE}/wp-json/wp/v2/tags",
                json={"name": name}, timeout=10,
            )
            if r2.ok:
                ids.append(r2.json()["id"])
                print(f"     [태그 신규생성] {name!r} → ID={ids[-1]}")
    return ids


def build_content(body_html: str, calc_slug: str) -> str:
    """inject_cta_and_links 후 Gutenberg 래핑"""
    calc_name = get_calc_name(calc_slug)
    body_html, report = inject_cta_and_links(body_html, calc_slug, calc_name)
    cta = "✅" if report["cta_inserted"] else "⚠️(이미 존재)"
    lnk = f"✅{report['internal_links_count']}개" if report["links_inserted"] else "⚠️(이미 존재)"
    print(f"     CTA={cta}  내부링크={lnk}")
    return f"<!-- wp:html -->\n{body_html}\n<!-- /wp:html -->"


def update_one(prefix: str, calc_slug: str, keyword: str, post_id: int) -> dict:
    print(f"\n[{prefix}] {keyword} (ID={post_id})")

    # 1. 로컬 HTML 로드
    html_files = sorted(ARTS_DIR.glob(f"{prefix}_*.html"))
    req_files  = sorted(REQS_DIR.glob(f"{prefix}_*.json"))
    if not html_files:
        print(f"     ❌ HTML 없음 — SKIP")
        return {"prefix": prefix, "status": "SKIP", "reason": "HTML 없음"}

    body_html = html_files[0].read_text(encoding="utf-8")
    seo = {}
    if req_files:
        req_data = json.loads(req_files[0].read_text(encoding="utf-8"))
        seo = req_data.get("seo", {})
    excerpt = seo.get("seo_description", "")
    title   = seo.get("seo_title", keyword)

    regen = "재생성" if prefix in REGEN_PREFIXES else "후처리"
    print(f"     {regen} | HTML={html_files[0].name} ({len(body_html)}자)")

    # 2. CTA + 내부링크 삽입
    content = build_content(body_html, calc_slug)

    # 3. 카테고리/태그 ID 조회
    cat_entry = _CAT_MAP.get(calc_slug, {})
    cat_names = cat_entry.get("categories", [])
    tag_names = cat_entry.get("tags", [])
    cat_ids = _resolve_wp_category_ids(cat_names) if cat_names else []
    tag_ids = _resolve_wp_tag_ids(tag_names) if tag_names else []
    if cat_ids:
        print(f"     카테고리: {cat_names} → IDs={cat_ids}")
    if tag_ids:
        print(f"     태그: {tag_names[:3]} → IDs={tag_ids[:3]}")

    # 4. WP PUT 업데이트
    payload: dict = {"content": content}
    if title:
        payload["title"] = title
    if excerpt:
        payload["excerpt"] = excerpt
    if cat_ids:
        payload["categories"] = cat_ids
    if tag_ids:
        payload["tags"] = tag_ids

    try:
        r = SESSION.post(
            f"{WP_BASE}/wp-json/wp/v2/posts/{post_id}",
            json=payload, timeout=30,
        )
        r.raise_for_status()
        updated = r.json()
        url = updated.get("link", "")
        print(f"     ✅ 업데이트 완료 → {url}")
        return {
            "prefix": prefix, "status": "OK", "post_id": post_id,
            "url": url, "cat_ids": cat_ids, "tag_ids": tag_ids,
            "regen": regen,
        }
    except Exception as e:
        print(f"     ❌ 업데이트 실패: {e}")
        return {"prefix": prefix, "status": "FAIL", "error": str(e)}


def main():
    print("=" * 70)
    print("Phase 5-E STEP 3: 10개 WordPress 업데이트")
    print(f"시작: {datetime.now().isoformat()}")
    print("=" * 70)

    results = []
    for prefix, calc_slug, keyword, post_id in ARTICLE_MAP:
        r = update_one(prefix, calc_slug, keyword, post_id)
        results.append(r)

    print("\n" + "=" * 70)
    print("업데이트 결과")
    print("=" * 70)
    for r in results:
        icon = "✅" if r.get("status") == "OK" else "❌"
        print(f"[{r.get('prefix','?')}] {icon} {r.get('status','?')} "
              f"cats={r.get('cat_ids',[])} tags={r.get('tag_ids',[])[:3]}")
        if r.get("url"):
            print(f"     {r['url']}")

    ok = sum(1 for r in results if r.get("status") == "OK")
    fail = len(results) - ok
    print(f"\n총계: OK={ok} / FAIL={fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(main())
