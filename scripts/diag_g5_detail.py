#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""내부링크 엔진 raw 반환값 세부 확인용 — 발행완료 URL 상태 점검"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from modules.config_loader import load_config
from modules.internal_link_engine import generate_related_calculators, generate_related_articles
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository
from repositories.article_repository import ArticleRepository

cfg = load_config()
db = get_db_adapter(cfg)

# 1. 계산기 published_url
calc_repo = CalculatorRepository(db)
calcs = calc_repo.get_active()
print(f"Active calcs: {len(calcs)}")
for c in calcs[:7]:
    url = c.get("published_url", "")
    print(f"  {c.get('name','?')}: published_url={repr(url[:70] if url else '')}")

# 2. 기사 발행 URL
art_repo = ArticleRepository(db)
rows = art_repo.get_all()
published = [r for r in rows if r.get("상태값") in ("발행완료", "검수대기")]
print(f"\nPublished articles: {len(published)}")
for r in published[:7]:
    url = r.get("발행 URL", "")
    print(f"  [{r.get('상태값','')}] {r.get('정책명','?')}: url={repr(url[:70] if url else '')}")

# 3. generate_related_articles 원시 반환
print("\n--- generate_related_articles('주휴수당 계산법', 3) ---")
raw = generate_related_articles(cfg, "주휴수당 계산법", 3)
print(f"  반환 건수: {len(raw)}")
for item in raw:
    print(f"  title={repr(item.get('title',''))[:40]} url={repr(item.get('url',''))[:60]}")

# 4. generate_related_calculators 원시 반환
print("\n--- generate_related_calculators('calc_20260702221622_621a', 3) ---")
raw2 = generate_related_calculators(cfg, "calc_20260702221622_621a", 3)
print(f"  반환 건수: {len(raw2)}")
for item in raw2:
    print(f"  name={repr(item.get('name',''))[:30]} url={repr(item.get('url',''))[:60]}")
