"""
modules/sheet_sync.py — ArticleRepository 브릿지
기존 호출부(main.py) 수정 없이 동작. gspread 직접 호출 제거.
"""
from adapters.db.factory import get_db_adapter
from repositories.article_repository import ArticleRepository


def _repo(cfg: dict) -> ArticleRepository:
    return ArticleRepository(get_db_adapter(cfg))


def read_test(cfg: dict) -> bool:
    return get_db_adapter(cfg).read_test()

def get_recent_titles(cfg: dict, n: int = 30) -> list[str]:
    return _repo(cfg).get_recent_published_titles(n)

def append_row(cfg: dict, row_data: dict):
    repo = _repo(cfg)
    article_id = row_data.get("ID") or row_data.get("마스터ID", "")
    if article_id:
        repo.update_status(article_id, row_data.get("상태값", "발행완료"), extra=row_data)
    else:
        repo.save(row_data)

def append_log(cfg: dict, log: dict):
    db = get_db_adapter(cfg)
    from datetime import datetime
    import uuid
    db.insert("logs", {
        "로그ID":    log.get("로그ID", uuid.uuid4().hex[:8]),
        "실행일시":  log.get("실행일시", datetime.now().isoformat()),
        "마스터ID":  log.get("마스터ID", ""),
        "대상정책명": log.get("대상 정책명", ""),
        "가동결과":  log.get("가동 결과", ""),
        "실패모듈":  log.get("실패 모듈명", ""),
        "오류내용":  log.get("오류 원인 내용", ""),
        "발행URL":   log.get("발행 URL (성공 시)", ""),
        "소요시간":  str(log.get("총 소요시간(초)", "")),
        "토큰합계":  str(log.get("사용 토큰 합계", "")),
    })

def get_all_posts(cfg: dict) -> list[dict]:
    return _repo(cfg).get_all()

def update_status(cfg: dict, row_index: int, status: str, extra: dict = None):
    # row_index 기반 업데이트는 Adapter 추상화 이후 ID 기반으로 전환됨
    # 기존 호환성 유지를 위해 전체 조회 후 index 매핑
    db = get_db_adapter(cfg)
    rows = db.get_all("articles")
    if 0 < row_index - 2 < len(rows):
        article_id = rows[row_index - 2].get("ID", "")
        if article_id:
            _repo(cfg).update_status(article_id, status, extra)