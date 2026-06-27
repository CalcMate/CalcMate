"""
adapters/storage/base.py — Storage Adapter 추상 인터페이스
전환: config.yaml  STORAGE_ADAPTER: drive → local → s3
"""
from abc import ABC, abstractmethod
from pathlib import Path


class AbstractStorageAdapter(ABC):

    @abstractmethod
    def save_file(self, local_path: Path, remote_name: str, folder: str = "") -> str:
        """파일 저장. public URL 또는 로컬 경로 반환"""

    @abstractmethod
    def load_file(self, remote_id: str, dest_path: Path):
        """파일 다운로드"""

    @abstractmethod
    def delete_file(self, remote_id: str):
        """파일 삭제"""

    @abstractmethod
    def backup_file(self, local_path: Path, backup_folder: str) -> str:
        """백업 저장. 저장 경로 반환"""

    @abstractmethod
    def read_test(self) -> bool:
        """연결 헬스체크"""
