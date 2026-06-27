"""
adapters/storage/factory.py — config 기반 Storage Adapter 선택
"""
from .base import AbstractStorageAdapter


def get_storage_adapter(cfg: dict) -> AbstractStorageAdapter:
    adapter_type = cfg.get("STORAGE_ADAPTER", "drive").lower()
    if adapter_type == "drive":
        from .drive_adapter import DriveAdapter
        return DriveAdapter(cfg)
    elif adapter_type == "local":
        from .local_adapter import LocalAdapter
        return LocalAdapter(cfg)
    elif adapter_type == "s3":
        from .s3_adapter import S3Adapter
        return S3Adapter(cfg)
    else:
        raise ValueError(f"알 수 없는 STORAGE_ADAPTER: {adapter_type}")
