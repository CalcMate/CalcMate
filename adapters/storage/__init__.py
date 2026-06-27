"""
adapters/storage/__init__.py — Storage Adapter 팩토리
STORAGE_ADAPTER: drive  → DriveAdapter (기본값)
STORAGE_ADAPTER: local  → LocalAdapter (홈서버 전환 후)
"""
from .base import AbstractStorageAdapter
from .drive_adapter import DriveAdapter
from .local_adapter import LocalAdapter


def get_storage_adapter(cfg: dict) -> AbstractStorageAdapter:
    adapter_type = cfg.get("STORAGE_ADAPTER", "drive").lower()
    if adapter_type == "local":
        return LocalAdapter(cfg)
    else:
        return DriveAdapter(cfg)
