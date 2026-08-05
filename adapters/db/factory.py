"""
adapters/db/factory.py — config 기반 DB Adapter 선택
"""
from .base import AbstractDBAdapter


def get_db_adapter(cfg: dict) -> AbstractDBAdapter:
    adapter_type = cfg.get("DB_ADAPTER", "sheets").lower()
    if adapter_type == "sheets":
        from .sheets_adapter import SheetsAdapter
        return SheetsAdapter(cfg)
    elif adapter_type == "sqlite":
        from .sqlite_adapter import SQLiteAdapter
        return SQLiteAdapter(cfg)
    elif adapter_type == "postgres":
        from .postgres_adapter import PostgresAdapter
        return PostgresAdapter(cfg)
    elif adapter_type == "dual":
        from .dual_adapter import DualAdapter
        return DualAdapter(cfg)
    else:
        raise ValueError(f"알 수 없는 DB_ADAPTER: {adapter_type}")
