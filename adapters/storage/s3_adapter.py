"""
adapters/storage/s3_adapter.py — S3 Compatible Storage 구현체 (stub)
AWS S3 / MinIO / Cloudflare R2 지원. pip install boto3 필요.
config.yaml:  STORAGE_ADAPTER: s3
"""
from pathlib import Path
from .base import AbstractStorageAdapter


class S3Adapter(AbstractStorageAdapter):
    """stub — 로컬 어댑터 안정화 후 구현"""
    def __init__(self, cfg: dict):
        self._cfg = cfg

    def save_file(self, local_path: Path, remote_name: str, folder: str = "") -> str:
        raise NotImplementedError("S3Adapter: 구현 예정")

    def load_file(self, remote_id: str, dest_path: Path):
        raise NotImplementedError

    def delete_file(self, remote_id: str):
        raise NotImplementedError

    def backup_file(self, local_path: Path, backup_folder: str) -> str:
        raise NotImplementedError

    def read_test(self) -> bool:
        return False
