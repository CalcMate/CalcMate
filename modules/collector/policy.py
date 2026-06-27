"""
modules/collector/policy.py — 정부정책 RSS 수집기
기존 rss_collector.py 로직 이관. 하위 호환 유지.
"""
import feedparser
from .base import BaseCollector


class PolicyCollector(BaseCollector):
    def collect(self, cfg: dict, site: dict = None) -> list[dict]:
        site = site or {}
        # 사이트별 RSS / fallback: config.yaml RSS_SOURCE_LIST
        import json
        raw = site.get("rss_sources") or ""
        try:
            sources = json.loads(raw) if raw else []
        except Exception:
            sources = []
        if not sources:
            sources = cfg.get("RSS_SOURCE_LIST", [])

        max_items = cfg.get("RSS_MAX_ITEMS_PER_SOURCE", 20)
        results = []
        for url in sources:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:max_items]:
                    results.append({
                        "title":       entry.get("title", ""),
                        "description": entry.get("summary", entry.get("description", "")),
                        "link":        entry.get("link", ""),
                        "published":   entry.get("published", ""),
                        "category":    _guess_category(entry),
                        "source_type": "policy",
                        "site_id":     site.get("site_id", ""),
                    })
            except Exception as e:
                print(f"[PolicyCollector] {url} 수집 오류: {e}")
        return results


def _guess_category(entry) -> str:
    tags = [t.get("term", "") for t in entry.get("tags", [])]
    return tags[0] if tags else "기타"
