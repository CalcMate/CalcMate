# -*- coding: utf-8 -*-
"""modules/registry_loader.py — calculator_registry 통합 로더 (작업지시서 E §1)

두 소스를 merge해서 slug→entry dict 반환:
  - docs/legal_basis.draft.yaml : 사람 큐레이션(검증된 legal). 코드가 쓰지 않음(읽기 전용). **우선**.
  - docs/registry_auto.yaml      : App Factory(save_app)가 자동생성. 사람이 직접 편집하지 않음.

동일 slug가 양쪽에 있으면 **큐레이션(legal_basis.draft.yaml)이 항상 우선**.
→ 사람이 자동엔트리를 정식 검증해 legal_basis.draft.yaml로 "승격"하면 그게 최종본이 되고,
   registry_auto.yaml의 임시 엔트리는 자동으로 무시됨.

app_generator / calculator_pipeline / publish_quality 세 로더가 이 함수에 위임(단일 소스).
"""
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent
_CURATED_PATH = _BASE / "docs" / "legal_basis.draft.yaml"
_AUTO_PATH = _BASE / "docs" / "registry_auto.yaml"

_cache = None


def _read_yaml(path: Path) -> dict:
    """YAML 파일 → dict(schema_version 제거). 없거나 파싱 실패 시 {}."""
    try:
        import yaml
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    data.pop("schema_version", None)
    return data


def load_registry(force: bool = False) -> dict:
    """slug→entry. auto 위에 curated를 덮어써 curated 우선. 1회 캐시(force=True 시 재로딩)."""
    global _cache
    if _cache is None or force:
        merged = dict(_read_yaml(_AUTO_PATH))      # 자동 먼저
        merged.update(_read_yaml(_CURATED_PATH))   # 큐레이션이 덮어씀(동일 slug 우선)
        _cache = merged
    return _cache


def invalidate():
    """캐시 무효화(App Factory가 registry_auto.yaml에 쓴 직후 등)."""
    global _cache
    _cache = None
