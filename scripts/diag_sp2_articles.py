# -*- coding: utf-8 -*-
"""SP-2 - 발행 기사(31개) 중 연말정산/육아휴직 forbidden_articles 포함 여부 확인"""
import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.article_repository import ArticleRepository

cfg = load_config()
db = get_db_adapter(cfg)

# forbidden_articles per slug (legal_basis.draft.yaml 기준)
FORBIDDEN_MAP = {
    "severance-pay":           ["근로기준법 제34조"],
    "육아휴직_급여_계산기":     ["고용보험법 제40조", "근로기준법 제74조"],
    "연말정산_환급액_계산기":   ["소득세법 제55조", "소득세법 제63조"],
}
ALL_FORBIDDEN = []
for v in FORBIDDEN_MAP.values():
    ALL_FORBIDDEN.extend(v)

def norm(s): return re.sub(r"\s+", "", str(s or ""))

art_repo = ArticleRepository(db)
articles = art_repo.get_all()
print(f"전체 아티클: {len(articles)}개")

print("\n모든 아티클 — calculator_id / status / forbidden 검사:")
print(f"{'ID':>5} {'slug':30} {'status':12} {'forbidden?'}")
print("-"*70)

hits = []
for art in articles:
    slug = str(art.get("calculator_id") or art.get("slug") or "unknown")
    status = str(art.get("status") or art.get("publish_status") or "?")
    wp_id = art.get("wp_post_id") or ""
    aid = art.get("id", "?")
    body = str(art.get("body_html") or art.get("body") or art.get("content") or "")
    body_norm = norm(body)

    found = [f for f in ALL_FORBIDDEN if norm(f) in body_norm]
    tag = f"[발견: {found}]" if found else "-"
    print(f"{str(aid):>5} {slug:30} {status:12} {tag}")
    if found:
        hits.append({"id": aid, "slug": slug, "status": status, "wp_id": wp_id, "found": found})

print(f"\n[forbidden 혼입 아티클 수]: {len(hits)}건")
if hits:
    for h in hits:
        print(f"  - id={h['id']}  slug={h['slug']}  status={h['status']}  wp_id={h['wp_id']}")
        print(f"    발견: {h['found']}")
else:
    print("  발행/DB 아티클에서 forbidden_articles 혼입 없음")

# 슬러그별 집계
slugs_seen = {}
for art in articles:
    slug = str(art.get("calculator_id") or art.get("slug") or "?")
    slugs_seen[slug] = slugs_seen.get(slug, 0) + 1
print("\n슬러그별 아티클 수:")
for s, cnt in sorted(slugs_seen.items()):
    print(f"  {s}: {cnt}건")
