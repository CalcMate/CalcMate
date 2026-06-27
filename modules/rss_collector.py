"""
rss_collector.py — STEP 1: RSS 수집
"""
import feedparser
from datetime import datetime

def collect(cfg: dict) -> list[dict]:
    sources = cfg.get("RSS_SOURCE_LIST", [])
    max_items = cfg.get("RSS_MAX_ITEMS_PER_SOURCE", 20)
    results = []
    for url in sources:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                results.append({
                    "title": entry.get("title", ""),
                    "description": entry.get("summary", entry.get("description", "")),
                    "link": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "category": _guess_category(entry),
                })
        except Exception as e:
            print(f"[RSS] {url} 수집 오류: {e}")
    return results

def _guess_category(entry) -> str:
    tags = [t.get("term", "") for t in entry.get("tags", [])]
    return tags[0] if tags else "기타"
