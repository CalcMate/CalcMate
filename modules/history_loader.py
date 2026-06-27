"""
history_loader.py — STEP 4: 최근 발행 내역 로드 (v11.5 분리)
"""
from .sheet_sync import get_recent_titles

def load_recent_titles(cfg: dict, n: int = 30) -> list[str]:
    try:
        return get_recent_titles(cfg, n)
    except Exception as e:
        print(f"[history_loader] 최근 발행 내역 로드 실패: {e}")
        return []
