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


_WP_IMAGE_RE = re.compile(
    r"<!--\s*wp:image\b.*?-->\s*<figure.*?</figure>\s*<!--\s*/wp:image\s*-->",
    re.DOTALL,
)


def extract_image_blocks(content: str) -> list[tuple[str, str]]:
    """기존 content에서 wp:image 블록과 직전 H2 텍스트를 추출 (MINOR-2: 보존용).

    반환: [(이미지 블록 원문, 직전 H2 텍스트 또는 ""), ...]
    """
    blocks = []
    for m in _WP_IMAGE_RE.finditer(content):
        before = content[: m.start()]
        h2s = list(re.finditer(r"<h2[^>]*>(.*?)</h2>", before, re.DOTALL))
        anchor = re.sub(r"<[^>]+>", "", h2s[-1].group(1)).strip() if h2s else ""
        blocks.append((m.group(0), anchor))
    return blocks


def set_img_alt(block: str, alt: str) -> str:
    """wp:image 블록 내 <img ... alt="..."> 의 alt 값 갱신 (MINOR-1)."""
    if not alt:
        return block
    return re.sub(r'(<img\b[^>]*\salt=")[^"]*(")', rf"\g<1>{alt}\g<2>", block, count=1)


def merge_image_blocks(body_html: str, blocks: list[tuple[str, str]], alt: str = "") -> str:
    """새 본문에 기존 wp:image 블록을 보존한다.

    - 중복 방지: 동일 src 이미지가 새 본문에 이미 있으면 스킵 (Case C)
    - 위치: 원래 직전 H2 텍스트를 새 본문에서 찾아 그 직후에 삽입 (Case A)
    - H2를 못 찾으면 본문 끝에 추가
    """
    for block, anchor in blocks:
        src_m = re.search(r'<img\b[^>]*\bsrc="([^"]+)"', block)
        src = src_m.group(1) if src_m else ""
        if src and src in body_html:
            continue  # 중복 방지
        block = set_img_alt(block, alt)
        if anchor:
            m = re.search(rf"(<h2[^>]*>{re.escape(anchor)}</h2>)", body_html)
            if m:
                pos = m.end()
                body_html = body_html[:pos] + "\n\n" + block + "\n" + body_html[pos:]
                continue
        body_html = body_html.rstrip() + "\n\n" + block
    return body_html


def build_content(body_html: str, calc_slug: str,
                  image_blocks: list[tuple[str, str]] | None = None,
                  body_alt: str = "") -> str:
    """inject_cta_and_links 후 Gutenberg 래핑. 기존 wp:image 블록은 보존한다."""
    calc_name = get_calc_name(calc_slug)
    body_html, report = inject_cta_and_links(body_html, calc_slug, calc_name)
    cta = "✅" if report["cta_inserted"] else "⚠️(이미 존재)"
    lnk = f"✅{report['internal_links_count']}개" if report["links_inserted"] else "⚠️(이미 존재)"
    print(f"     CTA={cta}  내부링크={lnk}")
    body_html = merge_image_blocks(body_html, image_blocks or [], body_alt)
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
    req_data = {}
    if req_files:
        req_data = json.loads(req_files[0].read_text(encoding="utf-8"))
        seo = req_data.get("seo", {})
    excerpt = seo.get("seo_description", "")
    title   = seo.get("seo_title", keyword)

    regen = "재생성" if prefix in REGEN_PREFIXES else "후처리"
    print(f"     {regen} | HTML={html_files[0].name} ({len(body_html)}자)")

    # 2a. 기존 WP 게시본에서 wp:image 블록 추출 (MINOR-2: 이미지 유실 방지)
    image_blocks: list[tuple[str, str]] = []
    try:
        cur = SESSION.get(
            f"{WP_BASE}/wp-json/wp/v2/posts/{post_id}?context=edit", timeout=10,
        )
        cur.raise_for_status()
        image_blocks = extract_image_blocks(cur.json().get("content", {}).get("raw", ""))
        print(f"     기존 이미지 블록: {len(image_blocks)}개")
    except Exception as e:
        print(f"     ⚠️ 기존 content 조회 실패 (이미지 블록 미보존): {e}")

    # 2b. request JSON의 body alt 텍스트 (MINOR-1)
    body_alt = ""
    img_info = (req_data.get("images") or {}).get("body") or {}
    if isinstance(img_info, dict):
        body_alt = img_info.get("alt", "") or ""

    # 3. CTA + 내부링크 삽입 (+ 이미지 블록 보존)
    content = build_content(body_html, calc_slug, image_blocks, body_alt)

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
