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
    global _cache, _lm_cache, _reg_cache
    _cache = None
    _lm_cache = None
    _reg_cache = None


# ── Sprint B-1: legal_master/ + registry/ 병행 로더(SSOT 신구조) ──────────
# 기존 load_registry(slug 단위 legal_basis.draft.yaml)와 별개로 추가만 함(프로덕션 영향 0).
# resolve(slug) 가 기존 load_registry().get(slug) 와 동일 결과를 내도록 설계(검증됨).
_LM_DIR = _BASE / "docs" / "legal_master"
_REG_DIR = _BASE / "docs" / "registry"
_lm_cache = None
_reg_cache = None


def _read_dir(d: Path) -> dict:
    """디렉토리 내 *.yaml 을 merge(키=entity_id 또는 slug). 없으면 {}."""
    merged = {}
    if d.exists():
        for f in sorted(d.glob("*.yaml")):
            part = _read_yaml(f)   # schema_version 제거 포함
            if isinstance(part, dict):
                merged.update(part)
    return merged


def load_legal_master(force: bool = False) -> dict:
    """entity_id → 법령필드 dict. legal_master/*.yaml merge. 1회 캐시."""
    global _lm_cache
    if _lm_cache is None or force:
        _lm_cache = _read_dir(_LM_DIR)
    return _lm_cache


def load_registry_v3(force: bool = False) -> dict:
    """slug → 계산기필드(+legal_refs) dict. registry/*.yaml merge. 1회 캐시."""
    global _reg_cache
    if _reg_cache is None or force:
        _reg_cache = _read_dir(_REG_DIR)
    return _reg_cache


def resolve(slug: str, force: bool = False) -> dict | None:
    """slug → (참조 법령 필드 + 계산기 필드) 병합 dict. 기존 load_registry().get(slug)와 동등.
    법령 필드 먼저, 계산기 필드 나중(겹침 없음). 신구조 미존재 시 None."""
    reg = load_registry_v3(force)
    r = reg.get(slug)
    if r is None:
        return None
    merged: dict = {}
    for ref in r.get("legal_refs", []) or []:
        merged.update(load_legal_master(force).get(ref, {}))
    merged.update(r)   # 계산기 필드(legal_refs 포함)
    return merged


_AUTO_HEADER = (
    "# registry_auto.yaml — App Factory 자동생성 계산기 registry (작업지시서 E §1)\n"
    "#\n"
    "# ⚠️ 이 파일은 App Factory(modules/app_factory.save_app)가 자동으로 씁니다. 사람이 직접 편집하지 마세요.\n"
    "# 자동생성 엔트리는 legal(law/article/authority 등) 전부 null + needs_human_legal: true 입니다.\n"
    "# 정식 legal 검증이 끝나면 해당 slug를 docs/legal_basis.draft.yaml 로 '승격'해서 옮겨 적으세요\n"
    "# (동일 slug는 legal_basis.draft.yaml 이 우선하므로, 승격 후 이 파일의 항목은 자동으로 무시됩니다).\n"
)


def add_auto_entry(slug: str, entry: dict) -> None:
    """registry_auto.yaml에 엔트리 추가/갱신(PyYAML safe_dump — 자동생성 전용이라 포맷 보존 불필요).
    헤더 주석 재삽입, 캐시 무효화. slug가 이미 있으면 덮어씀(재생성 대응)."""
    import yaml
    data = _read_yaml(_AUTO_PATH)   # 기존 엔트리(없으면 {})
    data[str(slug)] = entry
    body = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
    _AUTO_PATH.write_text(_AUTO_HEADER + "\n" + body, encoding="utf-8")
    invalidate()
