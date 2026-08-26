# -*- coding: utf-8 -*-
"""tests/test_registry_db_consistency.py — docs/registry/*_af.yaml ↔ DB calculators 정합성.

STEP 15-F/G에서 확인된 사실: Registry(YAML)와 DB(calculators 테이블)는 생성 시점에만
같은 값을 각각 독립적으로 기록하고, 이후 자동 동기화가 전혀 없다(app_factory.py 확인
완료). 이 파일은 그 divergence를 사후에라도 탐지하기 위한 검사다.

정책: 기본은 WARNING(테스트를 실패시키지 않음) — 일부 App-Factory 계산기는
registry input_labels가 비어 있거나 실제 runtime 필드와 1:1 대응하지 않는 경우가
있어 전체 강제 FAIL은 과하다(STEP 15-G에서 이미 검토한 판단). annual-leave-remaining
은 STEP 15-C~F에서 발견된 실제 불일치를 회귀 문서화 목적으로 xfail로 명시한다 —
DB가 실제로 갱신되면 이 테스트는 XPASS로 뒤집히고, 그때 strict=True 때문에 CI가
"마커를 지워야 한다"고 알려준다(수정 완료를 놓치지 않기 위한 장치).

DB는 읽기 전용으로만 접근한다(get_all/get_by_slug류). UPDATE/INSERT/DELETE 없음.
"""
import glob
import json
import warnings
from pathlib import Path

import pytest
import yaml

from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from repositories.calculator_repository import CalculatorRepository

ROOT = Path(__file__).resolve().parent.parent
AF_REGISTRY_GLOB = str(ROOT / "docs" / "registry" / "*_af.yaml")


def _load_af_entries():
    entries = []
    for path in sorted(glob.glob(AF_REGISTRY_GLOB)):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            continue
        for slug, entry in data.items():
            if isinstance(entry, dict):
                entries.append((Path(path).name, slug, entry))
    return entries


def _db_calcs_by_slug():
    cfg = load_config()
    repo = CalculatorRepository(get_db_adapter(cfg))
    return {c.get("slug"): c for c in repo.get_all()}


def _pj(v):
    if isinstance(v, dict):
        return v
    try:
        return json.loads(v) if v else {}
    except Exception:
        return {}


def test_registry_input_labels_vs_db_input_schema_warns_on_mismatch():
    """WARNING 정책: registry input_labels가 있는 App-Factory 계산기 전체를 훑어
    DB input_schema 키 집합과 다르면 경고만 출력(테스트 실패시키지 않음)."""
    db_calcs = _db_calcs_by_slug()
    mismatches = []
    for filename, slug, entry in _load_af_entries():
        input_labels = entry.get("input_labels") or []
        if not input_labels:
            continue  # registry에 입력 필드 명시가 없으면 비교 대상 아님
        calc = db_calcs.get(slug)
        if not calc:
            continue  # DB에 아직 없는 계산기(설계만 된 registry entry 등)
        db_keys = set(_pj(calc.get("input_schema")).keys())
        registry_keys = set(input_labels)
        if registry_keys != db_keys:
            mismatches.append((filename, slug, registry_keys, db_keys))

    for filename, slug, rk, dk in mismatches:
        warnings.warn(
            f"registry↔DB input_schema 불일치: {filename}:{slug} — "
            f"registry={sorted(rk)}, DB={sorted(dk)}",
            UserWarning,
        )
    # WARNING 정책 — 실패시키지 않음. 발견된 건수만 눈에 보이게 남김.
    print(f"\nregistry↔DB input_schema 불일치 {len(mismatches)}건 (WARNING만, FAIL 아님)")


def test_annual_leave_remaining_registry_matches_db_input_schema():
    """STEP 15-I에서 DB input_schema를 months_of_service 기준으로 갱신 완료
    (이전엔 xfail로 이 불일치를 문서화했으나, 실제 DB 수정 후 XPASS로 전환되어
    마커를 제거하고 정상 PASS 테스트로 승격함)."""
    db_calcs = _db_calcs_by_slug()
    calc = db_calcs.get("annual-leave-remaining")
    assert calc is not None, "annual-leave-remaining DB row를 찾지 못함"
    db_keys = set(_pj(calc.get("input_schema")).keys())
    # STEP 15-D/E 설계상 목표 스키마
    expected_keys = {"months_of_service", "used_days"}
    assert db_keys == expected_keys, f"DB input_schema={sorted(db_keys)} (목표={sorted(expected_keys)})"
