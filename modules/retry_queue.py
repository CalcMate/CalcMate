# -*- coding: utf-8 -*-
"""
modules/retry_queue.py — WordPress 발행 재시도 큐 (v12 Lite, 신규)

WordPress 발행 실패 시 발행 페이로드(title/html/meta/image)를 pending_posts에 저장하고
Dashboard에서 재발행할 수 있게 한다. publisher.publish를 그대로 재사용(원본 미변경).

저장: data/retry/pending_posts.json
"""
import json
import uuid
from datetime import datetime
from pathlib import Path

from .logger import get_logger

LOG = get_logger()
_PATH = Path(__file__).resolve().parent.parent / "data" / "retry" / "pending_posts.json"


def _load() -> list:
    if _PATH.exists():
        try:
            return json.loads(_PATH.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save(items: list):
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def enqueue(seo: dict, html: str, image_urls: dict = None, error: str = "") -> str:
    """발행 실패분을 큐에 저장. 반환: pending id."""
    items = _load()
    pid = datetime.now().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:4]
    items.append({
        "id": pid,
        "seo": seo, "html": html, "image_urls": image_urls or {},
        "error": str(error)[:300], "created_at": datetime.now().isoformat(),
        "status": "pending",
    })
    _save(items)
    LOG.info("[retry] 발행 대기 등록: %s (%s)", pid, seo.get("seo_title", ""))
    return pid


def list_pending() -> list:
    return [i for i in _load() if i.get("status") == "pending"]


def remove(pid: str):
    _save([i for i in _load() if i.get("id") != pid])


def retry(cfg: dict, pid: str) -> tuple:
    """publisher.publish 재시도. 성공 시 큐에서 제거. (ok, message)."""
    items = _load()
    item = next((i for i in items if i.get("id") == pid), None)
    if not item:
        return False, "대기 항목 없음"
    try:
        from . import publisher
        res = publisher.publish(datetime.now().strftime("%Y%m%d%H%M%S"),
                                item["seo"], item["html"], item.get("image_urls", {}), cfg)
        if res.get("status") == "published":
            remove(pid)
            return True, f"재발행 성공: {res.get('wordpress','')}"
        return False, f"미발행({res.get('status')}) — WordPress 설정 확인"
    except Exception as e:
        for i in items:
            if i["id"] == pid:
                i["error"] = str(e)[:300]
        _save(items)
        LOG.warning("[retry] 재발행 실패 %s: %s", pid, e)
        return False, f"재발행 실패: {e}"
