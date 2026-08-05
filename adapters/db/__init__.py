"""
adapters/db/__init__.py — DB Adapter 패키지
실제 선택 로직은 factory.py에 단일화. 이 파일은 re-export 전용.

DB_ADAPTER: sheets   → SheetsAdapter
DB_ADAPTER: sqlite   → SQLiteAdapter
DB_ADAPTER: postgres → PostgresAdapter
DB_ADAPTER: dual     → DualAdapter (Sheets primary + SQLite secondary)
"""
from .base import AbstractDBAdapter
from .factory import get_db_adapter  # 단일 진입점 — dual 포함 모든 어댑터 지원

__all__ = ["AbstractDBAdapter", "get_db_adapter"]
