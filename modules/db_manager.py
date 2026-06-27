"""
modules/db_manager.py — ArticleRepository 브릿지
기존 DBManager 인터페이스 유지. gspread 직접 호출 제거.
"""
from adapters.db.factory import get_db_adapter
from repositories.article_repository import ArticleRepository


class DBManager:
    def __init__(self, cfg: dict):
        self._db   = get_db_adapter(cfg)
        self._repo = ArticleRepository(self._db)

    def get_all_rows(self) -> list[dict]:
        return self._repo.get_all()

    def get_pending_rows(self) -> list[dict]:
        return self._repo.get_pending()

    def get_top_pending(self) -> dict | None:
        return self._repo.get_top_pending()

    def get_recent_published_titles(self, n: int = 30) -> list[str]:
        return self._repo.get_recent_published_titles(n)

    def get_row_by_id(self, post_id: str) -> tuple:
        row = self._repo.get_by_id(post_id)
        return (row, -1) if not row else (row, 0)

    def save_post_data(self, post_info: dict) -> str:
        return self._repo.save(post_info)

    def update_post_status(self, post_id: str, status: str, extra: dict = None):
        self._repo.update_status(post_id, status, extra)

    def add_row_if_not_exists(self, policy_name: str, source_url: str,
                               score: float, site_id: str = "") -> str:
        return self._repo.upsert_by_policy_name(policy_name, source_url, score, site_id)

    def increment_fail_count(self, post_id: str) -> int:
        return self._repo.increment_fail(post_id)

    def read_test(self) -> bool:
        return self._db.read_test()
