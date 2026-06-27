"""
modules/collector/factory.py — source_type → Collector 라우팅
새 타입 추가 시 이 파일에 한 줄만 추가.
"""
from .base import BaseCollector


_REGISTRY: dict[str, type] = {}


def register(source_type: str, cls: type):
    _REGISTRY[source_type] = cls


def get_collector(source_type: str) -> BaseCollector:
    if not _REGISTRY:
        _bootstrap()
    cls = _REGISTRY.get(source_type)
    if cls is None:
        print(f"[CollectorFactory] 알 수 없는 source_type '{source_type}' → PolicyCollector fallback")
        cls = _REGISTRY["policy"]
    return cls()


def _bootstrap():
    from .policy     import PolicyCollector
    from .calculator import CalculatorCollector
    from .affiliate  import AffiliateCollector
    from .finance    import FinanceCollector
    register("policy",     PolicyCollector)
    register("calculator", CalculatorCollector)
    register("affiliate",  AffiliateCollector)
    register("finance",    FinanceCollector)
    register("custom",     PolicyCollector)   # custom → policy fallback
