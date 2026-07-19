# -*- coding: utf-8 -*-
"""SP-2 영향 범위 조사 — 발행된 퇴직금 관련 WordPress 글에 "근로기준법 제34조" 포함 여부 확인"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository
from repositories.article_repository import ArticleRepository

cfg = load_config()
db = get_db_adapter(cfg)

FORBIDDEN = "근로기준법제34조"  # 정규화(공백 제거)
VARIATIONS = [
    "근로기준법 제34조",
    "근로기준법제34조",
    "근로기준법 제34조의2",
    "근로기준법제34조의2",
    "제34조의2",
    "제34 조",  # 공백 변형
]

def norm(s): return re.sub(r"\s+", "", str(s or ""))

print("="*70)
print(" SP-2 영향 범위 조사 — 발행 글 내 '근로기준법 제34조' 포함 여부")
print("="*70)

# 발행된 아티클 전수 조회
try:
    art_repo = ArticleRepository(db)
    articles = art_repo.get_all()
    print(f"\n[ArticleRepository] 전체 아티클 수: {len(articles)}개")

    hits = []
    for art in articles:
        slug = str(art.get("calculator_id") or art.get("slug") or "")
        status = str(art.get("status") or art.get("publish_status") or "")
        wp_id = art.get("wp_post_id") or art.get("wordpress_post_id") or ""
        body = str(art.get("body_html") or art.get("body") or art.get("content") or "")
        title = str(art.get("title") or art.get("seo_title") or "")

        body_norm = norm(body)
        found_vars = []
        for var in VARIATIONS:
            if norm(var) in body_norm:
                found_vars.append(var)

        if found_vars:
            hits.append({
                "id": art.get("id", "?"),
                "slug": slug,
                "title": title[:40],
                "status": status,
                "wp_id": wp_id,
                "found": found_vars,
            })

    print(f"\n[결과] '근로기준법 제34조' 계열 발견: {len(hits)}건")
    for h in hits:
        print(f"  - ID={h['id']}  slug={h['slug']}  status={h['status']}  wp_id={h['wp_id']}")
        print(f"    title: {h['title']}")
        print(f"    발견 표기: {h['found']}")

    if not hits:
        print("  발행된 글 중 해당 문자열 없음")

    # 퇴직금 관련 발행글만 따로 표시
    severance_arts = [a for a in articles if "severance" in str(a.get("calculator_id","")).lower()
                      or "퇴직" in str(a.get("title",""))]
    print(f"\n[퇴직금 관련 아티클 전체] {len(severance_arts)}건:")
    for a in severance_arts:
        print(f"  ID={a.get('id')}  status={a.get('status') or a.get('publish_status')}  "
              f"wp_id={a.get('wp_post_id')}  title={str(a.get('title',''))[:50]}")

except Exception as e:
    print(f"[ERROR] ArticleRepository 조회 실패: {e}")
    import traceback; traceback.print_exc()

# 계산기 DB 확인 (faq/body 필드)
print("\n" + "="*70)
print(" 계산기 DB — severance-pay faq/body 필드 내 '제34조' 확인")
print("="*70)
try:
    calc_repo = CalculatorRepository(db)
    calcs = calc_repo.get_all()
    sp = next((c for c in calcs if c.get("slug") == "severance-pay"), None)
    if sp:
        faq = str(sp.get("faq") or "")
        body = str(sp.get("body") or sp.get("description") or "")
        content = str(sp.get("content") or "")
        for field_name, val in [("faq", faq), ("body", body), ("content", content)]:
            val_norm = norm(val)
            found = [v for v in VARIATIONS if norm(v) in val_norm]
            status_tag = f"[발견: {found}]" if found else "[없음]"
            print(f"  {field_name} {status_tag}  (길이={len(val)})")
    else:
        print("  severance-pay 계산기 DB 항목 없음")
except Exception as e:
    print(f"[ERROR] CalculatorRepository 조회 실패: {e}")
