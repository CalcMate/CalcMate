# -*- coding: utf-8 -*-
"""
Phase 3 — WordPress 브랜드 업데이트 스크립트
실행 시점: calcmate.kr 라이브 서버 연결 완료 후

작업 내용:
  1. 사이트 제목 / Tagline 변경
  2. 기존 발행 Post 본문의 SalaryMate → CalcMate 일괄 치환
  3. 결과 보고

사용법:
  python scripts/phase3_wp_rebrand.py           # dry-run (변경 없음, 확인만)
  python scripts/phase3_wp_rebrand.py --apply   # 실제 변경 적용
"""
import sys, re, argparse
sys.stdout.reconfigure(encoding="utf-8")

try:
    import requests
except ImportError:
    print("[ERROR] requests 패키지 필요: pip install requests")
    sys.exit(1)

from pathlib import Path
BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
from modules.config_loader import load_config

# ── 설정 로드 ──────────────────────────────────────────────────
cfg = load_config()
WP_URL   = cfg.get("WORDPRESS_URL", "").rstrip("/")
WP_USER  = cfg.get("WORDPRESS_USERNAME", "")
WP_PW    = (cfg.get("WORDPRESS_APP_PASSWORD")
            or (cfg.get("wordpress") or {}).get("app_password", ""))
HEADERS  = {"Content-Type": "application/json"}
AUTH     = (WP_USER, WP_PW)

OLD_BRAND = "SalaryMate"
NEW_BRAND = "CalcMate"

def _api(method: str, path: str, **kwargs):
    url = f"{WP_URL}/wp-json/{path}"
    r = getattr(requests, method)(url, auth=AUTH, headers=HEADERS, timeout=15, **kwargs)
    r.raise_for_status()
    return r.json()


def check_connection():
    print(f"WP URL: {WP_URL}")
    try:
        _api("get", "wp/v2/posts?per_page=1")
        print("연결: OK")
        return True
    except Exception as e:
        print(f"연결 실패: {e}")
        return False


def update_site_settings(dry_run: bool):
    """사이트 제목 / Tagline 업데이트."""
    print("\n[1] 사이트 설정 확인 ─────")
    try:
        settings = _api("get", "wp/v2/settings")
        title   = settings.get("title", "")
        tagline = settings.get("description", "")
        print(f"  현재 제목: {title!r}")
        print(f"  현재 태그라인: {tagline!r}")

        updates = {}
        if OLD_BRAND in title:
            updates["title"] = title.replace(OLD_BRAND, NEW_BRAND)
        if OLD_BRAND in tagline:
            updates["description"] = tagline.replace(OLD_BRAND, NEW_BRAND)

        if not updates:
            print("  변경 필요 없음")
        elif dry_run:
            print(f"  [DRY-RUN] 변경 예정: {updates}")
        else:
            _api("post", "wp/v2/settings", json=updates)
            print(f"  변경 완료: {updates}")
    except Exception as e:
        print(f"  [WARN] settings API 접근 불가: {e}")
        print("  수동으로 WordPress 관리자 > 설정 > 일반에서 변경 필요")


def update_posts(dry_run: bool):
    """발행된 Post 본문의 SalaryMate → CalcMate 치환."""
    print("\n[2] Post 본문 업데이트 ─────")
    page = 1
    total_updated = 0
    while True:
        try:
            posts = _api("get", f"wp/v2/posts?per_page=20&page={page}&context=edit&status=any")
        except Exception as e:
            print(f"  포스트 조회 실패(page {page}): {e}")
            break
        if not posts:
            break
        for post in posts:
            pid   = post["id"]
            ptitle = (post.get("title") or {}).get("raw", "")
            raw   = (post.get("content") or {}).get("raw", "")
            changed = False
            new_title = ptitle
            new_raw   = raw

            if OLD_BRAND in ptitle:
                new_title = ptitle.replace(OLD_BRAND, NEW_BRAND)
                changed = True
            if OLD_BRAND in raw:
                new_raw = raw.replace(OLD_BRAND, NEW_BRAND)
                changed = True

            if changed:
                total_updated += 1
                print(f"  pid={pid} '{ptitle[:40]}' ─ 치환 {'예정' if dry_run else '완료'}")
                if not dry_run:
                    try:
                        _api("post", f"wp/v2/posts/{pid}",
                             json={"title": new_title, "content": new_raw})
                    except Exception as e:
                        print(f"    [ERROR] pid={pid} 업데이트 실패: {e}")
        page += 1
        if len(posts) < 20:
            break

    print(f"  총 {total_updated}건 {'변경 예정' if dry_run else '변경 완료'}")


def update_pages(dry_run: bool):
    """페이지(소개/Footer 등) 내 브랜드명 치환."""
    print("\n[3] 페이지 업데이트 ─────")
    page = 1
    total_updated = 0
    while True:
        try:
            pages = _api("get", f"wp/v2/pages?per_page=20&page={page}&context=edit")
        except Exception as e:
            print(f"  페이지 조회 실패: {e}")
            break
        if not pages:
            break
        for pg in pages:
            pid  = pg["id"]
            pttl = (pg.get("title") or {}).get("raw", "")
            raw  = (pg.get("content") or {}).get("raw", "")
            changed = False
            new_title = pttl
            new_raw   = raw
            if OLD_BRAND in pttl:
                new_title = pttl.replace(OLD_BRAND, NEW_BRAND)
                changed = True
            if OLD_BRAND in raw:
                new_raw = raw.replace(OLD_BRAND, NEW_BRAND)
                changed = True
            if changed:
                total_updated += 1
                print(f"  page_id={pid} '{pttl[:40]}' ─ 치환 {'예정' if dry_run else '완료'}")
                if not dry_run:
                    try:
                        _api("post", f"wp/v2/pages/{pid}",
                             json={"title": new_title, "content": new_raw})
                    except Exception as e:
                        print(f"    [ERROR] page_id={pid} 업데이트 실패: {e}")
        page += 1
        if len(pages) < 20:
            break
    print(f"  총 {total_updated}건 {'변경 예정' if dry_run else '변경 완료'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 3 WP 리브랜딩")
    parser.add_argument("--apply", action="store_true", help="실제 변경 적용 (없으면 dry-run)")
    args = parser.parse_args()
    dry_run = not args.apply

    print("=" * 60)
    print(f"Phase 3 WP 리브랜딩 — {'DRY-RUN' if dry_run else '실제 적용'}")
    print("=" * 60)

    if not check_connection():
        print("\n[중단] WordPress 서버에 연결할 수 없습니다.")
        print("  확인: Laragon 실행 여부, config.yaml의 WORDPRESS_URL/USERNAME/APP_PASSWORD")
        sys.exit(1)

    update_site_settings(dry_run)
    update_posts(dry_run)
    update_pages(dry_run)

    print("\n" + "=" * 60)
    if dry_run:
        print("DRY-RUN 완료. 실제 적용: python scripts/phase3_wp_rebrand.py --apply")
    else:
        print("Phase 3 WP 리브랜딩 완료.")
        print("다음: 브라우저 개발자도구에서 JSON-LD Organization name 확인")
