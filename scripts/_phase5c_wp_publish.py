# -*- coding: utf-8 -*-
"""Phase 5-C 10개 아티클 WordPress Published 게시 스크립트

- status: publish (Draft 아님)
- 중복 slug 체크 후 Skip
- 이미지 업로드 (thumb -> featured_media, body -> inline)
- 본문 H2 지정 위치에 body 이미지 삽입
- CTA 블록 + 내부링크 자동 삽입 (cta_builder)
- 카테고리 자동지정 (calculator_categories.yaml)
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

import yaml
import requests as req

BASE = Path(__file__).parent.parent
REQUESTS_DIR = BASE / "data" / "phase5-c" / "requests"
ARTICLES_DIR = BASE / "data" / "phase5-c" / "articles"
_CATEGORIES_YAML = BASE / "config" / "calculator_categories.yaml"

sys.path.insert(0, str(BASE))
from modules.cta_builder import inject_cta_and_links
from modules.law_ssot import get_calc_name

WP_BASE  = "http://127.0.0.1"
WP_HOST  = "salarymate.test"
WP_AUTH  = ("geminia", "IfSt cfZ4 CVT5 sqTi DFdj bx4j")
COMMON_HEADERS = {"Host": WP_HOST}

ARTICLE_ORDER = [
    "01", "02", "03", "04", "05",
    "06", "07", "08", "09", "10",
]


# ── WordPress 헬퍼 ─────────────────────────────────────────────────────────────

def _session() -> req.Session:
    s = req.Session()
    s.auth = WP_AUTH
    s.headers.update(COMMON_HEADERS)
    return s


SESSION = _session()

# ── 카테고리 매핑 로드 ─────────────────────────────────────────────────────────

def _load_categories_map() -> dict:
    """calculator_categories.yaml 로드 → {slug: {categories: [...], tags: [...]}}"""
    if not _CATEGORIES_YAML.exists():
        return {}
    return yaml.safe_load(_CATEGORIES_YAML.read_text(encoding="utf-8")) or {}


_CAT_MAP = _load_categories_map()


def wp_get_json(path: str, **params) -> list | dict:
    r = SESSION.get(f"{WP_BASE}/wp-json/wp/v2/{path}", params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def wp_post_json(path: str, payload: dict) -> dict:
    r = SESSION.post(f"{WP_BASE}/wp-json/wp/v2/{path}", json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def upload_media(img_path: Path) -> dict:
    """WebP 이미지 WordPress 업로드 -> {id, url}"""
    with open(img_path, "rb") as f:
        data = f.read()
    headers = {
        "Host": WP_HOST,
        "Content-Disposition": f'attachment; filename="{img_path.name}"',
        "Content-Type": "image/webp",
    }
    r = req.post(
        f"{WP_BASE}/wp-json/wp/v2/media",
        auth=WP_AUTH, headers=headers, data=data, timeout=60,
    )
    r.raise_for_status()
    d = r.json()
    return {"id": d["id"], "url": d["source_url"]}


def check_slug_exists(slug: str) -> dict | None:
    """기존 게시물 slug 확인 (publish/draft 모두)"""
    results = wp_get_json("posts", slug=slug, status="any", per_page=5)
    return results[0] if results else None


def _resolve_wp_category_ids(category_names: list[str]) -> list[int]:
    """카테고리명 목록 → WordPress category ID 목록. 없으면 신규 생성."""
    ids: list[int] = []
    for name in category_names:
        results = SESSION.get(
            f"{WP_BASE}/wp-json/wp/v2/categories",
            params={"search": name, "per_page": 5},
            timeout=10,
        ).json()
        # 이름이 정확히 일치하는 항목 우선
        match = next((r for r in results if r.get("name") == name), None)
        if match:
            ids.append(match["id"])
        else:
            # 신규 생성
            try:
                r = SESSION.post(
                    f"{WP_BASE}/wp-json/wp/v2/categories",
                    json={"name": name},
                    timeout=10,
                )
                r.raise_for_status()
                ids.append(r.json()["id"])
                print(f"     [카테고리 신규생성] '{name}' -> ID={ids[-1]}")
            except Exception as e:
                print(f"     [카테고리 생성 실패] '{name}': {e}")
    return ids


def _resolve_wp_tag_ids(tag_names: list[str]) -> list[int]:
    """태그명 목록 → WordPress tag ID 목록. 없으면 신규 생성."""
    ids: list[int] = []
    for name in tag_names:
        results = SESSION.get(
            f"{WP_BASE}/wp-json/wp/v2/tags",
            params={"search": name, "per_page": 5},
            timeout=10,
        ).json()
        match = next((r for r in results if r.get("name") == name), None)
        if match:
            ids.append(match["id"])
        else:
            try:
                r = SESSION.post(
                    f"{WP_BASE}/wp-json/wp/v2/tags",
                    json={"name": name},
                    timeout=10,
                )
                r.raise_for_status()
                ids.append(r.json()["id"])
                print(f"     [태그 신규생성] '{name}' -> ID={ids[-1]}")
            except Exception as e:
                print(f"     [태그 생성 실패] '{name}': {e}")
    return ids


# ── 슬러그 생성 ───────────────────────────────────────────────────────────────

def make_slug(keyword: str) -> str:
    """키워드 -> WordPress slug (소문자, 하이픈)"""
    s = keyword.strip().lower()
    s = re.sub(r"[^\w\s가-힣]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s


# ── 본문 이미지 삽입 ─────────────────────────────────────────────────────────

def insert_body_image(html: str, img_url: str, after_h2: str) -> str:
    """지정 H2 다음에 이미지 블록 삽입"""
    img_block = (
        f'\n<!-- wp:image {{"sizeSlug":"full"}} -->\n'
        f'<figure class="wp-block-image size-full">'
        f'<img src="{img_url}" alt="" /></figure>\n'
        f'<!-- /wp:image -->\n'
    )
    if after_h2:
        pattern = re.compile(
            r"(<h2[^>]*>" + re.escape(after_h2) + r"</h2>)",
            re.IGNORECASE | re.DOTALL,
        )
        if pattern.search(html):
            html = pattern.sub(r"\1" + img_block, html, count=1)
            return html
    # fallback: 맨 앞에 삽입
    return img_block + html


def build_gutenberg(
    body_html: str,
    img_url: str | None,
    after_h2: str,
    calc_slug: str = "",
) -> str:
    """Gutenberg 블록 형식으로 본문 조립 (이미지 + CTA + 내부링크 포함)"""
    if img_url:
        body_html = insert_body_image(body_html, img_url, after_h2)

    # CTA + 내부링크 자동삽입
    if calc_slug:
        calc_name = get_calc_name(calc_slug)
        body_html, cta_report = inject_cta_and_links(body_html, calc_slug, calc_name)
        if cta_report["cta_inserted"]:
            print(f"     CTA 삽입 완료: {calc_slug}")
        if cta_report["links_inserted"]:
            print(f"     내부링크 {cta_report['internal_links_count']}개 삽입")

    return f"<!-- wp:html -->\n{body_html}\n<!-- /wp:html -->"


# ── 메인 ─────────────────────────────────────────────────────────────────────

def load_article(num: str) -> dict | None:
    """num(01-10) 기준으로 request JSON + HTML + 이미지 경로 로드"""
    req_files = sorted(REQUESTS_DIR.glob(f"{num}_*.json"))
    html_files = sorted(ARTICLES_DIR.glob(f"{num}_*.html"))

    if not req_files or not html_files:
        print(f"  [SKIP] {num}: JSON={bool(req_files)}, HTML={bool(html_files)}")
        return None

    meta = json.loads(req_files[0].read_text(encoding="utf-8"))
    body_html = html_files[0].read_text(encoding="utf-8")

    seo = meta.get("seo", {})
    images = meta.get("images", {})
    thumb_meta = images.get("thumbnail", {})
    body_meta  = images.get("body", {})

    thumb_path = Path(thumb_meta["path"]) if thumb_meta.get("path") else None
    body_path  = Path(body_meta["path"])  if body_meta.get("path")  else None

    calc_slug = meta.get("slug", "")
    return {
        "num"        : num,
        "keyword"    : meta.get("keyword", ""),
        "slug"       : make_slug(meta.get("keyword", "")),
        "calc_slug"  : calc_slug,          # 계산기 slug (CTA/카테고리용)
        "title"      : seo.get("seo_title", meta.get("keyword", "")),
        "excerpt"    : seo.get("seo_description", ""),
        "body_html"  : body_html,
        "thumb_path" : thumb_path,
        "body_path"  : body_path,
        "insert_h2"  : body_meta.get("insert_after_h2", ""),
        "thumb_alt"  : thumb_meta.get("alt", ""),
        "body_alt"   : body_meta.get("alt", ""),
    }


def publish_one(art: dict) -> dict:
    num   = art["num"]
    slug  = art["slug"]
    title = art["title"]

    print(f"\n[{num}] {art['keyword']}")
    print(f"     slug: {slug}")

    # 1. 중복 확인
    existing = check_slug_exists(slug)
    if existing:
        print(f"     DUPLICATE: ID={existing['id']} status={existing['status']}")
        return {
            "num": num, "keyword": art["keyword"], "slug": slug,
            "status": "DUPLICATE", "post_id": existing["id"],
            "url": existing.get("link", ""), "note": "기존 게시물 유지"
        }

    # 2. 썸네일 업로드
    featured_id = None
    if art["thumb_path"] and art["thumb_path"].exists():
        try:
            r = upload_media(art["thumb_path"])
            featured_id = r["id"]
            print(f"     thumb  -> media ID={featured_id}")
        except Exception as e:
            print(f"     thumb 업로드 실패: {e}")
    else:
        print(f"     thumb 없음: {art['thumb_path']}")

    # 3. 본문 이미지 업로드
    body_img_url = None
    if art["body_path"] and art["body_path"].exists():
        try:
            r = upload_media(art["body_path"])
            body_img_url = r["url"]
            print(f"     body   -> {body_img_url}")
        except Exception as e:
            print(f"     body img 업로드 실패: {e}")
    else:
        print(f"     body img 없음: {art['body_path']}")

    # 4. Gutenberg 본문 조립 (CTA + 내부링크 포함)
    calc_slug = art.get("calc_slug", "")
    content = build_gutenberg(art["body_html"], body_img_url, art["insert_h2"], calc_slug=calc_slug)

    # 5. 카테고리/태그 ID 조회
    cat_names = _CAT_MAP.get(calc_slug, {}).get("categories", [])
    tag_names  = _CAT_MAP.get(calc_slug, {}).get("tags", [])
    category_ids = _resolve_wp_category_ids(cat_names) if cat_names else []
    tag_ids      = _resolve_wp_tag_ids(tag_names) if tag_names else []
    if category_ids:
        print(f"     카테고리: {cat_names} → IDs={category_ids}")
    if tag_ids:
        print(f"     태그: {tag_names} → IDs={tag_ids}")

    # 6. 게시
    payload = {
        "title"   : title,
        "slug"    : slug,
        "content" : content,
        "excerpt" : art["excerpt"],
        "status"  : "publish",
    }
    if featured_id:
        payload["featured_media"] = featured_id
    if category_ids:
        payload["categories"] = category_ids
    if tag_ids:
        payload["tags"] = tag_ids

    try:
        post = wp_post_json("posts", payload)
        pid  = post["id"]
        url  = post["link"]
        print(f"     PUBLISHED: ID={pid}")
        print(f"     URL: {url}")
        return {
            "num": num, "keyword": art["keyword"], "slug": slug,
            "status": "PUBLISHED", "post_id": pid, "url": url,
            "has_thumb": featured_id is not None,
            "has_body_img": body_img_url is not None,
        }
    except Exception as e:
        print(f"     게시 실패: {e}")
        return {
            "num": num, "keyword": art["keyword"], "slug": slug,
            "status": "FAILED", "error": str(e)
        }


def main() -> int:
    print("Phase 5-C WordPress 게시")
    print("=" * 68)

    articles = []
    for num in ARTICLE_ORDER:
        art = load_article(num)
        if art:
            articles.append(art)

    results = []
    for art in articles:
        r = publish_one(art)
        results.append(r)

    # ── 최종 보고 ───────────────────────────────────────────────────────────
    print("\n" + "=" * 68)
    print("최종 결과")
    print("=" * 68)
    for r in results:
        thumb_ok = "O" if r.get("has_thumb") else "X"
        body_ok  = "O" if r.get("has_body_img") else "X"
        img_info = f"thumb={thumb_ok} body={body_ok}" if r["status"] == "PUBLISHED" else ""
        print(f"[{r['num']}] {r['status']:<12} ID={r.get('post_id','—'):<6} {img_info}")
        if r["status"] in ("PUBLISHED", "DUPLICATE"):
            print(f"       URL: {r.get('url','')}")

    print("\n브라우저 육안확인 URL 목록")
    print("-" * 68)
    for r in results:
        url = r.get("url", "")
        if url:
            print(f"[{r['num']}] {r['keyword']}")
            print(f"     {url}")

    fail_cnt = sum(1 for r in results if r["status"] == "FAILED")
    dup_cnt  = sum(1 for r in results if r["status"] == "DUPLICATE")
    ok_cnt   = sum(1 for r in results if r["status"] == "PUBLISHED")

    print(f"\n총계: PUBLISHED={ok_cnt} / DUPLICATE={dup_cnt} / FAILED={fail_cnt}")
    return fail_cnt


if __name__ == "__main__":
    sys.exit(main())
