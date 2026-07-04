"""
repositories/article_repository.py — ArticleRepository
마스터_DB CRUD. 기존 db_manager / sheet_sync 대체.
"""
import json
import uuid
from datetime import datetime
from adapters.db.base import AbstractDBAdapter

VALID_STATUSES = {
    "대기", "진행중", "작성중", "이미지오류", "작성오류",
    "발행완료", "발행실패", "복구대기", "보류", "만료", "재처리대기",
    "수정됨", "휴지통",
}

# 유효 발행 카운트에서 제외할 비활성 상태(삭제/휴지통 등). 상태 종류가 늘어나면
# 이 집합만 수정하면 되도록 Repository 계층에 둔다(파이프라인/엔진은 개수만 사용).
INACTIVE_ARTICLE_STATUSES = {"삭제됨", "휴지통", "발행취소"}


class ArticleRepository:
    TABLE = "articles"

    def __init__(self, db: AbstractDBAdapter):
        self._db = db

    def get_all(self) -> list[dict]:
        return self._db.get_all(self.TABLE)

    def get_pending(self) -> list[dict]:
        rows = self._db.get_where(self.TABLE, {"상태값": "대기"})
        rows.sort(key=lambda r: float(r.get("우선발행점수") or 0), reverse=True)
        return rows

    def get_top_pending(self) -> dict | None:
        rows = self.get_pending()
        return rows[0] if rows else None

    def get_recent_published_titles(self, n: int = 30) -> list[str]:
        rows = self._db.get_all(self.TABLE)
        published = [r for r in rows if r.get("상태값") == "발행완료"]
        published.sort(key=lambda r: r.get("발행일시") or "", reverse=True)
        return [r.get("최종추천제목", "") for r in published[:n]]

    def count_active_articles(self, calculator_id) -> int:
        """해당 계산기로 발행된 글 중 비활성('삭제됨' 등)을 제외한 유효 발행 건수.
        상태값 문자열 판단은 이 Repository 내부(INACTIVE_ARTICLE_STATUSES)에만 둔다 —
        파이프라인은 이 개수를 MAX_ARTICLES_PER_CALCULATOR와 비교만 한다."""
        cid = str(calculator_id or "").strip()
        if not cid:
            return 0
        rows = self._db.get_where(self.TABLE, {"calculator_id": cid})
        return sum(1 for r in rows
                   if str(r.get("상태값", "")).strip() not in INACTIVE_ARTICLE_STATUSES)

    def get_by_id(self, article_id: str) -> dict | None:
        rows = self._db.get_where(self.TABLE, {"ID": article_id})
        return rows[0] if rows else None

    def save(self, article: dict) -> str:
        if not article.get("ID"):
            article["ID"] = datetime.now().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:4]
        article.setdefault("상태값", "대기")
        article.setdefault("최종수정일", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        return self._db.insert(self.TABLE, article)

    def update_status(self, article_id: str, status: str, extra: dict = None):
        if status not in VALID_STATUSES:
            raise ValueError(f"유효하지 않은 상태값: {status}")
        data = {"상태값": status, "최종수정일": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        if extra:
            data.update(extra)
        self._db.update(self.TABLE, article_id, data)

    def upsert_by_policy_name(self, policy_name: str, source_url: str, score: float,
                               site_id: str = "") -> str:
        rows = self._db.get_where(self.TABLE, {"정책명": policy_name})
        if rows:
            return str(rows[0].get("ID", ""))
        return self.save({
            "정책명": policy_name,
            "원본출처": source_url,
            "우선발행점수": score,
            "site_id": site_id,
        })

    def append_history(self, article_id, event, extra=None):
        """기존 history(JSON 문자열)를 읽어 이벤트 1건 append 후 update_status의
        extra로 저장. article이 없거나 history가 비어있으면 빈 배열에서 시작."""
        row = self.get_by_id(article_id)
        hist = []
        try:
            hist = json.loads(row.get("history") or "[]") if row else []
        except Exception:
            hist = []
        entry = {"event": event, "at": datetime.now().isoformat()}
        if extra:
            entry.update(extra)
        hist.append(entry)
        # 상태값 검증(VALID_STATUSES)을 타지 않도록 update_status 대신 저수준 update 사용.
        # 상태값은 그대로 두고 history 필드만 갱신 → "검수대기" 등 어떤 상태에서도 안전.
        return self._db.update(self.TABLE, article_id,
                               {"history": json.dumps(hist, ensure_ascii=False)})

    def increment_fail(self, article_id: str) -> int:
        row = self.get_by_id(article_id)
        if not row:
            return 0
        log = row.get("상태변경로그", "")
        fail_count = log.count("FAIL:") + 1
        self._db.update(self.TABLE, article_id, {
            "상태변경로그": log + f" | FAIL:{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "상태값": "재처리대기" if fail_count >= 3 else "발행실패",
        })
        return fail_count
