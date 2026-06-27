"""
adapters/db/__init__.py — DB Adapter 팩토리
config.yaml의 DB_ADAPTER 값으로 구현체 자동 선택.

DB_ADAPTER: sheets   → SheetsAdapter (기본값)
DB_ADAPTER: sqlite   → SQLiteAdapter (홈서버 초기)
DB_ADAPTER: postgres → PostgresAdapter (홈서버 안정화 후)
"""
from .base import AbstractDBAdapter
from .sheets_adapter import SheetsAdapter
from .sqlite_adapter import SQLiteAdapter
from .postgres_adapter import PostgresAdapter


def get_db_adapter(cfg: dict) -> AbstractDBAdapter:
    adapter_type = cfg.get("DB_ADAPTER", "sheets").lower()
    if adapter_type == "sqlite":
        return SQLiteAdapter(cfg)
    elif adapter_type == "postgres":
        return PostgresAdapter(cfg)
    else:
        return SheetsAdapter(cfg)
