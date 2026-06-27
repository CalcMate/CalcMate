# -*- coding: utf-8 -*-
"""
modules/dashboard_cache.py — 대시보드 읽기 캐시(SQLite 미러)  [UI 가속 전용]

★ 기능/출력/파이프라인 불변. 읽기 성능만 개선.
구조:
    [Dashboard] ─읽기(즉시)→ [SQLite 미러(data/cache/dashboard_cache.db)]
                              ▲ 주기 sync (scripts/sync_cache.bat / refresh())
                              └─ get_db_adapter(cfg)(=Sheets 등 원본)

정확성 보장:
- 미러가 신선(ttl 이내)하면 미러 반환(빠름).
- 미러가 없거나 오래되면 원본을 1회 조회→미러 갱신→반환(출력 동일).
- 원본 조회 실패(예: Sheets 403)면 마지막 미러(stale)라도 반환(크래시 방지). 미러도 없으면 [].
- 쓰기/액션 후 invalidate_all()로 다음 읽기에서 강제 갱신.
미러는 별도 파일이라 원본 데이터(시트/프로젝트 sqlite)에 영향 없음.
"""
import json
import sqlite3
import time
from pathlib import Path

from .logger import get_logger

LOG = get_logger()

TABLES = ["articles", "calculators", "sites", "logs", "app_templates"]


def _db_path(cfg: dict) -> Path:
    root = Path(cfg.get("_root", "."))
    d = root / "data" / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d / "dashboard_cache.db"


def _conn(cfg: dict):
    c = sqlite3.connect(str(_db_path(cfg)))
    c.execute("CREATE TABLE IF NOT EXISTS _cache "
              "(table_name TEXT PRIMARY KEY, rows_json TEXT, updated_at REAL)")
    return c


def _store(cfg: dict, table: str, rows: list):
    with _conn(cfg) as c:
        c.execute("INSERT OR REPLACE INTO _cache VALUES (?,?,?)",
                  (table, json.dumps(rows, ensure_ascii=False), time.time()))
        c.commit()


def _load(cfg: dict, table: str):
    """(rows, age_seconds) 또는 (None, None)."""
    try:
        with _conn(cfg) as c:
            r = c.execute("SELECT rows_json, updated_at FROM _cache WHERE table_name=?",
                          (table,)).fetchone()
        if not r:
            return None, None
        return json.loads(r[0]), (time.time() - float(r[1]))
    except Exception:
        return None, None


def read(cfg: dict, table: str, ttl: int = 120, auto_refresh: bool = True) -> list:
    """미러 우선 읽기. 신선하면 미러, 아니면 원본 1회 조회→미러 갱신(폴백 안전)."""
    rows, age = _load(cfg, table)
    if rows is not None and age is not None and age < ttl:
        return rows                      # 캐시 적중 (빠름)
    if not auto_refresh and rows is not None:
        return rows
    # 미스/만료 → 원본 조회 시도
    try:
        from adapters.db.factory import get_db_adapter
        live = get_db_adapter(cfg).get_all(table)
        _store(cfg, table, live)
        return live
    except Exception as e:
        LOG.warning("dashboard_cache: 원본 조회 실패(%s) → 미러 폴백: %s", table, e)
        return rows if rows is not None else []


def refresh(cfg: dict, tables: list = None) -> dict:
    """백그라운드 동기화: 원본→미러 갱신. {table: 행수 또는 'ERR'}"""
    out = {}
    from adapters.db.factory import get_db_adapter
    db = get_db_adapter(cfg)
    for t in (tables or TABLES):
        try:
            rows = db.get_all(t)
            _store(cfg, t, rows)
            out[t] = len(rows)
        except Exception as e:
            out[t] = f"ERR:{str(e)[:40]}"
    LOG.info("dashboard_cache refresh: %s", out)
    return out


def invalidate_all(cfg: dict):
    """모든 미러를 만료 처리(다음 읽기에서 강제 갱신)."""
    try:
        with _conn(cfg) as c:
            c.execute("UPDATE _cache SET updated_at = 0")
            c.commit()
    except Exception as e:
        LOG.warning("dashboard_cache invalidate 실패: %s", e)


def last_sync(cfg: dict) -> dict:
    """{table: age_seconds} 진단용."""
    out = {}
    for t in TABLES:
        _, age = _load(cfg, t)
        out[t] = round(age, 1) if age is not None else None
    return out


if __name__ == "__main__":
    # 백그라운드 동기화 단독 실행: python -m modules.dashboard_cache
    import yaml
    base = Path(__file__).resolve().parent.parent
    cfg = yaml.safe_load(open(base / "config" / "config.yaml", encoding="utf-8")) or {}
    cfg["_root"] = str(base)
    print(json.dumps(refresh(cfg), ensure_ascii=False))
