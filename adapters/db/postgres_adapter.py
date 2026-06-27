"""
adapters/db/postgres_adapter.py — PostgreSQL 구현체 (stub)
홈서버 확장 시 사용. pip install psycopg2-binary 필요.
config.yaml:  DB_ADAPTER: postgres
              POSTGRES_DSN: postgresql://user:pass@localhost:5432/blog_auto
"""
from .base import AbstractDBAdapter


class PostgresAdapter(AbstractDBAdapter):
    """
    stub — SQLite 운영 안정화 후 구현.
    인터페이스는 AbstractDBAdapter와 동일하므로 비즈니스 로직 수정 없음.
    """
    def __init__(self, cfg: dict):
        self._dsn = cfg.get("POSTGRES_DSN", "")
        # import psycopg2; self._pool = psycopg2.connect(self._dsn)

    def get_all(self, table: str) -> list[dict]:
        raise NotImplementedError("PostgresAdapter: 구현 예정")

    def get_where(self, table: str, filters: dict) -> list[dict]:
        raise NotImplementedError

    def insert(self, table: str, row: dict) -> str:
        raise NotImplementedError

    def update(self, table: str, row_id: str, data: dict):
        raise NotImplementedError

    def delete(self, table: str, row_id: str):
        raise NotImplementedError

    def read_test(self) -> bool:
        return False  # 미구현 명시
