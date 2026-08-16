# -*- coding: utf-8 -*-
"""WP 기존 게시물 현황 조회"""
import sys, re
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
import requests as req

WP_BASE = "http://127.0.0.1"
WP_HOST = "salarymate.test"
WP_AUTH = ("geminia", "IfSt cfZ4 CVT5 sqTi DFdj bx4j")

ARTICLES = [
    ("01", "퇴직금 받는 조건"),
    ("02", "주휴수당 계산법"),
    ("03", "실업급여 조건"),
    ("04", "4대보험 계산"),
    ("05", "연차수당 계산방법"),
    ("06", "퇴직금 신청서류"),
    ("07", "육아휴직 급여 조건"),
    ("08", "연말정산 환급액"),
    ("09", "실업급여 신청방법"),
    ("10", "4대보험 취득신고 서류"),
]


def make_slug(keyword: str) -> str:
    s = keyword.strip().lower()
    s = re.sub(r"[^\w\s가-힣]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s


def main():
    session = req.Session()
    session.auth = WP_AUTH
    session.headers["Host"] = WP_HOST

    # 연결 테스트
    try:
        r = session.get(f"{WP_BASE}/wp-json/wp/v2/posts", params={"per_page": 1}, timeout=5)
        r.raise_for_status()
        print(f"WP 연결 OK (HTTP {r.status_code})")
    except Exception as e:
        print(f"WP 연결 실패: {e}")
        return

    print(f"\n{'번':>3} {'ID':>6} {'status':<10} {'cats':>6} {'slug'}")
    print("-" * 70)
    results = {}
    for no, kw in ARTICLES:
        wp_slug = make_slug(kw)
        try:
            r = session.get(
                f"{WP_BASE}/wp-json/wp/v2/posts",
                params={"slug": wp_slug, "status": "any", "per_page": 3},
                timeout=10,
            )
            posts = r.json()
        except Exception as e:
            print(f"[{no}] 조회 실패: {e}")
            continue

        if posts:
            p = posts[0]
            pid = p["id"]
            status = p["status"]
            cats = p.get("categories", [])
            tags = p.get("tags", [])
            # 본문에 CTA 있는지 확인
            content_rendered = p.get("content", {}).get("rendered", "")
            has_cta = "<h2>계산기 사용하기</h2>" in content_rendered
            has_calcmate = "calcmate.kr" in content_rendered
            has_internal = 'class="internal-links"' in content_rendered
            print(
                f"[{no}] ID={pid:>5} {status:<10} cats={cats} tags={tags[:3]}"
            )
            print(
                f"     CTA={'✅' if has_cta else '❌'}  calcmate={'✅' if has_calcmate else '❌'}  "
                f"내부링크={'✅' if has_internal else '❌'}  slug={wp_slug}"
            )
            results[no] = {
                "id": pid, "status": status, "cats": cats, "tags": tags,
                "has_cta": has_cta, "has_calcmate": has_calcmate,
                "has_internal": has_internal, "slug": wp_slug,
            }
        else:
            print(f"[{no}] NOT FOUND — {wp_slug}")
            results[no] = {"id": None, "slug": wp_slug}

    return results


if __name__ == "__main__":
    main()
