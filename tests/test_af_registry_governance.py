# -*- coding: utf-8 -*-
"""tests/test_af_registry_governance.py — App Factory registry(*_af.yaml) 거버넌스 검증.

status=READY인데 review_checklist의 critical 항목이 checked:false로 남아있는
엔트리를 자동 탐지한다(정상 흐름이면 modules/app_factory.py의 promote_to_ready()가
이 상태를 만들 수 없으므로, 발견되면 registry 파일이 직접 편집되어 검토 게이트를
우회했다는 뜻이다 — annual-leave-remaining 사례 참고).

review_checklist 자체가 없는 엔트리는 대상에서 제외한다(promote_to_ready()도
checklist가 없으면 검사를 건너뛰므로 앱의 실제 게이트 동작과 일치시킴 — 이는
별개 문제이며 이 테스트의 범위가 아니다).
"""
import glob
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
AF_REGISTRY_GLOB = str(ROOT / "docs" / "registry" / "*_af.yaml")


def _load_af_entries():
    """(파일명, slug, entry) 튜플 목록 반환."""
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


def test_af_registry_files_exist():
    entries = _load_af_entries()
    assert entries, "docs/registry/*_af.yaml에서 엔트리를 찾지 못함"


def test_ready_entries_have_no_unchecked_critical_items():
    """status=READY + review_checklist 존재 + critical 항목 중 checked:false가
    하나라도 있으면 실패. HOLD 상태거나 checklist가 없는 엔트리는 대상 아님."""
    violations = []
    for filename, slug, entry in _load_af_entries():
        if entry.get("status") != "READY":
            continue
        checklist = entry.get("review_checklist") or []
        if not checklist:
            continue
        unchecked = [
            item.get("label", item.get("id", "?"))
            for item in checklist
            if item.get("severity") == "critical" and not item.get("checked")
        ]
        if unchecked:
            violations.append(f"{filename}:{slug} — 미확인 critical 항목: {unchecked}")

    assert not violations, (
        "READY 상태인데 critical review_checklist가 미완료인 엔트리 발견 "
        "(promote_to_ready() 게이트를 우회해 직접 편집됐을 가능성):\n"
        + "\n".join(violations)
    )


def test_legal_refs_point_to_existing_legal_master_entities():
    """STEP 15-H: registry의 legal_refs에 적힌 slug가 실제 docs/legal_master/*.yaml에
    존재하는지 확인(DB 접근 없는 순수 YAML 검사 — governance 테스트와 동일 성격이라
    별도 파일로 중복 만들지 않고 여기 병합)."""
    from modules.registry_loader import load_legal_master

    legal_master = load_legal_master(force=True)
    violations = []
    for filename, slug, entry in _load_af_entries():
        for ref in entry.get("legal_refs") or []:
            if ref not in legal_master:
                violations.append(f"{filename}:{slug} — legal_refs에 존재하지 않는 slug: {ref}")

    assert not violations, (
        "registry legal_refs가 docs/legal_master/*.yaml에 없는 엔티티를 참조:\n"
        + "\n".join(violations)
    )
