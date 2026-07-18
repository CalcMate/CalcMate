#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""DB 전체 상태 확인 — ArticleRepository.get_all() 원시 결과"""
import sys
from pathlib import Path
from collections import Counter

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.article_repository import ArticleRepository
from repositories.calculator_repository import CalculatorRepository

cfg = load_config()
db = get_db_adapter(cfg)

art_repo = ArticleRepository(db)
rows = art_repo.get_all()
print(f"Total rows in article repo: {len(rows)}")

if rows:
    statuses = Counter(r.get("상태값", "<empty>") for r in rows)
    print(f"상태값 분포: {dict(statuses)}")
    # 첫 2개 row의 전체 키 확인
    print(f"\n첫 번째 row keys: {list(rows[0].keys())[:15]}")
    # URL 필드명 탐색
    first = rows[0]
    for k, v in first.items():
        if "url" in str(k).lower() or "URL" in str(k) or "발행" in str(k):
            print(f"  URL관련 키: {repr(k)} = {repr(str(v)[:80])}")
else:
    print("rows is EMPTY")

# 혹시 다른 필드명?
if rows:
    pub_count = sum(1 for r in rows if r.get("상태값") in ("발행완료", "검수대기"))
    pub_count2 = sum(1 for r in rows if "발행" in str(r.get("상태값", "")))
    print(f"\n상태값=='발행완료'/'검수대기': {pub_count}")
    print(f"상태값 contains '발행': {pub_count2}")
