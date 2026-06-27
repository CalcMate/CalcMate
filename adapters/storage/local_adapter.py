"""
adapters/storage/local_adapter.py — 로컬 스토리지 구현체
홈서버 운영 시 사용. Google Drive 없이 로컬 SSD/NAS에 저장.
config.yaml:  STORAGE_ADAPTER: local
              LOCAL_STORAGE_ROOT: /data/blog_auto/storage
              LOCAL_STORAGE_BASE_URL: https://cdn.yourdomain.kr
"""
import shutil
from pathlib import Path
from datetime import datetime
from .base import AbstractStorageAdapter


class LocalAdapter(AbstractStorageAdapter):
    def __init__(self, cfg: dict):
        self._root = Path(cfg.get("LOCAL_STORAGE_ROOT", "data/storage"))
        self._base_url = cfg.get("LOCAL_STORAGE_BASE_URL", "").rstrip("/")
        self._root.mkdir(parents=True, exist_ok=True)

    def _dest(self, folder: str) -> Path:
        p = self._root / folder if folder else self._root
        p.mkdir(parents=True, exist_ok=True)
        return p

    def save_file(self, local_path: Path, remote_name: str, folder: str = "") -> str:
        dest = self._dest(folder) / remote_name
        shutil.copy2(str(local_path), str(dest))
        if self._base_url and folder:
            return f"{self._base_url}/{folder}/{remote_name}"
        return str(dest)

    def load_file(self, remote_id: str, dest_path: Path):
        shutil.copy2(remote_id, str(dest_path))

    def delete_file(self, remote_id: str):
        p = Path(remote_id)
        if p.exists():
            p.unlink()

    def backup_file(self, local_path: Path, backup_folder: str) -> str:
        return self.save_file(local_path, local_path.name, folder=backup_folder)

    def read_test(self) -> bool:
        try:
            return self._root.exists()
        except Exception:
            return False
