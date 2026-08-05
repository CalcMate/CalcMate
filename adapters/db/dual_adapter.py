"""
adapters/db/dual_adapter.py — Sheets(primary) + SQLite(secondary) 동시 쓰기

쓰기 전략:
  두 스토리지를 독립적으로 시도한다.
  - Sheets OK, SQLite 실패 → SQLite 재시도 큐(data/sync/pending_sync.json) 적재, Sheets 데이터 보존
  - SQLite OK, Sheets 실패 → SQLite 행에 sync_status='sync_pending' 마킹, 데이터 유실 없음
  - 둘 다 실패 → RuntimeError 전파(호출자가 처리)
읽기: Sheets 우선(최신성 보장). Sheets 다운 시 SQLite fallback.
config.yaml:  DB_ADAPTER: dual
"""
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

from .base import AbstractDBAdapter

LOG = logging.getLogger("dual_adapter")

_SYNC_QUEUE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "sync" / "pending_sync.json"


# ── 동기화 재시도 큐 ────────────────────────────────────────────

def _load_queue() -> list:
    if _SYNC_QUEUE_PATH.exists():
        try:
            return json.loads(_SYNC_QUEUE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save_queue(items: list):
    _SYNC_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SYNC_QUEUE_PATH.write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def enqueue_sync(op: str, table: str, row: dict, row_id: str = "", error: str = "") -> str:
    items = _load_queue()
    qid = datetime.now().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:4]
    items.append({
        "id": qid,
        "op": op,            # insert | update | delete
        "table": table,
        "row": row,
        "row_id": row_id,
        "error": str(error)[:300],
        "created_at": datetime.now().isoformat(),
        "status": "pending",
    })
    _save_queue(items)
    LOG.warning("[dual] 동기화 재시도 큐 적재: %s %s %s (error: %s)", op, table, row_id, str(error)[:80])
    return qid


def list_pending_sync() -> list:
    return [i for i in _load_queue() if i.get("status") == "pending"]


def remove_sync(qid: str):
    _save_queue([i for i in _load_queue() if i.get("id") != qid])


class DualAdapter(AbstractDBAdapter):
    """Primary: SheetsAdapter / Secondary: SQLiteAdapter."""

    def __init__(self, cfg: dict):
        from .sheets_adapter import SheetsAdapter
        from .sqlite_adapter import SQLiteAdapter
        self._primary = SheetsAdapter(cfg)
        self._secondary = SQLiteAdapter(cfg)

    # ── 읽기: Sheets 우선, 실패 시 SQLite fallback ────────────────
    def get_all(self, table: str, **kwargs) -> list[dict]:
        try:
            return self._primary.get_all(table, **kwargs)
        except Exception as e:
            LOG.warning("[dual] Sheets get_all 실패, SQLite fallback: %s", e)
            return self._secondary.get_all(table)

    def get_where(self, table: str, filters: dict) -> list[dict]:
        try:
            return self._primary.get_where(table, filters)
        except Exception as e:
            LOG.warning("[dual] Sheets get_where 실패, SQLite fallback: %s", e)
            return self._secondary.get_where(table, filters)

    # ── 쓰기: 독립 시도, 개별 실패 핸들링 ──────────────────────────
    def insert(self, table: str, row: dict) -> str:
        sheets_ok, local_ok = False, False
        sheets_id = ""

        try:
            sheets_id = self._primary.insert(table, row)
            sheets_ok = True
        except Exception as e:
            LOG.error("[dual] Sheets insert 실패: %s", e)
            # Sheets 실패 → local에 sync_pending 마킹
            try:
                self._secondary.insert(table, {**row, "sync_status": "sync_pending"})
                local_ok = True
                LOG.info("[dual] Sheets 실패 → 로컬 sync_pending 저장됨 (데이터 유실 없음)")
            except Exception as le:
                LOG.error("[dual] 로컬 fallback도 실패: %s", le)

        if sheets_ok:
            try:
                self._secondary.insert(table, {**row, "sync_status": "synced"})
                local_ok = True
            except Exception as le:
                LOG.warning("[dual] 로컬 insert 실패, 재시도 큐 적재: %s", le)
                enqueue_sync("insert", table, row, sheets_id, str(le))

        if not sheets_ok and not local_ok:
            raise RuntimeError(f"DualAdapter: both storages failed for insert({table})")

        return sheets_id or str(row.get("id", ""))

    def update(self, table: str, row_id: str, data: dict):
        sheets_ok = False
        try:
            self._primary.update(table, row_id, data)
            sheets_ok = True
        except Exception as e:
            LOG.error("[dual] Sheets update 실패: %s", e)
            try:
                self._secondary.update(table, row_id, {**data, "sync_status": "sync_pending"})
                LOG.info("[dual] Sheets 실패 → 로컬 sync_pending 갱신됨")
                return
            except Exception as le:
                raise RuntimeError(f"DualAdapter: both storages failed for update({table},{row_id})") from le

        if sheets_ok:
            try:
                self._secondary.update(table, row_id, data)
            except Exception as le:
                LOG.warning("[dual] 로컬 update 실패, 재시도 큐 적재: %s", le)
                enqueue_sync("update", table, data, row_id, str(le))

    def delete(self, table: str, row_id: str):
        try:
            self._primary.delete(table, row_id)
        except Exception as e:
            LOG.error("[dual] Sheets delete 실패: %s", e)
        try:
            self._secondary.delete(table, row_id)
        except Exception as le:
            LOG.warning("[dual] 로컬 delete 실패: %s", le)
            enqueue_sync("delete", table, {}, row_id, str(le))

    def read_test(self) -> bool:
        return self._primary.read_test()

    def invalidate_cache(self, table: str = None):
        if hasattr(self._primary, "invalidate_cache"):
            self._primary.invalidate_cache(table)
