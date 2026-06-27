"""
adapters/db/sqlite_adapter.py — SQLite 구현체
홈서버 초기 운영용. Google Sheets → SQLite 이전 시 사용.
config.yaml:  DB_ADAPTER: sqlite
              SQLITE_PATH: data/blog_auto.db
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from .base import AbstractDBAdapter

# 테이블별 id 컬럼명
_ID_COL = {
    "sites":             "site_id",
    "articles":          "ID",
    "calculators":       "id",
    "app_templates":     "template_id",
    "app_factory_queue": "job_id",
    "app_factory_logs":  "log_id",
}


class SQLiteAdapter(AbstractDBAdapter):
    def __init__(self, cfg: dict):
        db_path = cfg.get("SQLITE_PATH", "data/blog_auto.db")
        self._path = Path(cfg.get("_root", ".")) / db_path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _conn(self):
        conn = sqlite3.connect(str(self._path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_table(self, conn, table: str, row: dict):
        cols = ", ".join(f'"{k}" TEXT' for k in row.keys())
        conn.execute(f'CREATE TABLE IF NOT EXISTS "{table}" ({cols})')
        # 기존 테이블에 없는 컬럼 추가
        existing = {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
        for col in row.keys():
            if col not in existing:
                conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{col}" TEXT')
        conn.commit()

    def get_all(self, table: str) -> list[dict]:
        with self._conn() as conn:
            try:
                rows = conn.execute(f'SELECT * FROM "{table}"').fetchall()
                return [dict(r) for r in rows]
            except sqlite3.OperationalError:
                return []

    def get_where(self, table: str, filters: dict) -> list[dict]:
        rows = self.get_all(table)
        for col, val in filters.items():
            rows = [r for r in rows if str(r.get(col, "")) == str(val)]
        return rows

    def insert(self, table: str, row: dict) -> str:
        with self._conn() as conn:
            self._ensure_table(conn, table, row)
            cols = ", ".join(f'"{k}"' for k in row.keys())
            placeholders = ", ".join("?" for _ in row)
            conn.execute(
                f'INSERT INTO "{table}" ({cols}) VALUES ({placeholders})',
                list(str(v or "") for v in row.values())
            )
            conn.commit()
        id_col = _ID_COL.get(table, "id")
        return str(row.get(id_col, ""))

    def update(self, table: str, row_id: str, data: dict):
        id_col = _ID_COL.get(table, "id")
        if "updated_at" not in data:
            data["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f'"{k}" = ?' for k in data.keys())
        with self._conn() as conn:
            self._ensure_table(conn, table, data)   # 신규 컬럼 자동 추가(기존 컬럼 불변)
            conn.execute(
                f'UPDATE "{table}" SET {set_clause} WHERE "{id_col}" = ?',
                [*[str(v or "") for v in data.values()], str(row_id)]
            )
            conn.commit()

    def delete(self, table: str, row_id: str):
        id_col = _ID_COL.get(table, "id")
        with self._conn() as conn:
            conn.execute(f'DELETE FROM "{table}" WHERE "{id_col}" = ?', [str(row_id)])
            conn.commit()

    def read_test(self) -> bool:
        try:
            with self._conn() as conn:
                conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    def dump(self, dest_path: Path):
        """백업용 DB 덤프"""
        import shutil
        shutil.copy2(str(self._path), str(dest_path))
