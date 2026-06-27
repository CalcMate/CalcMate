"""
adapters/db/base.py — DB Adapter 추상 인터페이스
비즈니스 로직은 이 인터페이스만 알면 됨.
전환: config.yaml  DB_ADAPTER: sheets → sqlite → postgres
"""
from abc import ABC, abstractmethod


class AbstractDBAdapter(ABC):

    @abstractmethod
    def get_all(self, table: str) -> list[dict]:
        """테이블 전체 행 반환"""

    @abstractmethod
    def get_where(self, table: str, filters: dict) -> list[dict]:
        """조건 일치 행 반환. filters = {컬럼: 값} AND 조건"""

    @abstractmethod
    def insert(self, table: str, row: dict) -> str:
        """행 추가. 생성된 id 반환"""

    @abstractmethod
    def update(self, table: str, row_id: str, data: dict):
        """id 기준 컬럼 업데이트"""

    @abstractmethod
    def delete(self, table: str, row_id: str):
        """id 기준 행 삭제"""

    @abstractmethod
    def read_test(self) -> bool:
        """연결 헬스체크"""
