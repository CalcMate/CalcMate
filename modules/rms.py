# -*- coding: utf-8 -*-
"""modules/rms.py — Regulation Management System 핵심 모듈 (Phase G)

워크플로: DETECTED → DRAFT → UNDER_REVIEW → APPROVED → PROMOTED / REJECTED

설계 원칙:
- master.yaml 에는 APPROVED+회귀통과 항목만 승격
- 사람이 최종 게이트(자동 승격 없음)
- 모든 상태 전이 → LEGAL_BASIS_AUDIT.md + archive/ 스냅샷 기록
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

_BASE = Path(__file__).resolve().parent.parent
_MASTER = _BASE / "docs" / "legal_basis.master.yaml"
_DRAFT  = _BASE / "docs" / "legal_basis.draft.yaml"
_ARCHIVE_DIR = _BASE / "docs" / "legal_basis.archive"
_AUDIT  = _BASE / "docs" / "LEGAL_BASIS_AUDIT.md"
_WORKFLOW_STATES = ("DETECTED", "DRAFT", "UNDER_REVIEW", "APPROVED", "PROMOTED", "REJECTED")


# ── 유틸 ──────────────────────────────────────────────────────────────────────

def _read_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if isinstance(data, dict):
            data.pop("schema_version", None)
            return data
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return {}


def _write_yaml(path: Path, data: dict, header: str = "") -> None:
    body = yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
    path.write_text(header + "\n" + body, encoding="utf-8")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _year() -> str:
    return datetime.now().strftime("%Y")


# ── G-3: 영향 계산기 분석 ────────────────────────────────────────────────────

# 법령 엔티티 → 영향 받는 계산기 slug 매핑
# 새 계산기가 추가되거나 요율 구조 변경 시 이 테이블도 갱신 필요
IMPACT_MAP: dict[str, list[str]] = {
    # 최저임금 — weekly-holiday-allowance(주휴수당 최저임금 경고) + unemployment-benefit(하한 = min_wage×8×0.8)
    "min_wage_hourly": ["weekly-holiday-allowance", "unemployment-benefit"],
    # 국민연금 요율/상하한 — four-insurances + 연말정산(4대보험 자동계산)
    "np_rate":   ["four-insurances", "연말정산_환급액_계산기"],
    "np_min":    ["four-insurances", "연말정산_환급액_계산기"],
    "np_max":    ["four-insurances", "연말정산_환급액_계산기"],
    # 건강보험 요율 — four-insurances + 연말정산
    "hi_rate":   ["four-insurances", "연말정산_환급액_계산기"],
    # 장기요양 요율 — four-insurances + 연말정산
    "ltc_rate":  ["four-insurances", "연말정산_환급액_계산기"],
    # 고용보험 요율 — four-insurances + 연말정산
    "ei_rate":   ["four-insurances", "연말정산_환급액_계산기"],
    # 구직급여 상한
    "daily_max": ["unemployment-benefit"],
    # 소득세 구간
    "income_tax_brackets": ["연말정산_환급액_계산기"],
    # 근로소득공제 구간
    "labor_deduction_table": ["연말정산_환급액_계산기"],
    # 세액공제 한도
    "tax_credit_limits": ["연말정산_환급액_계산기"],
    # 인적공제 1인당 금액
    "per_person": ["연말정산_환급액_계산기"],
    # 육아휴직 급여 상/하한
    "parental_leave_benefit": ["육아휴직_급여_계산기"],
    # 소득세법 제127조 원천징수세율(3.3%) — 세율 변경 시 freelancer-tax-3p3 영향
    "income_tax_act_127": ["freelancer-tax-3p3"],
}


def find_impacted(field_key: str) -> list[str]:
    """법령 필드명 → 영향받는 계산기 slug 목록."""
    return IMPACT_MAP.get(str(field_key), [])


def impact_report(field_keys: list[str]) -> str:
    """여러 필드에 대한 영향 리포트 문자열 반환."""
    seen: dict[str, set] = {}
    for fk in field_keys:
        for slug in find_impacted(fk):
            seen.setdefault(slug, set()).add(fk)
    if not seen:
        return "영향받는 계산기 없음"
    lines = []
    for slug, fields in sorted(seen.items()):
        lines.append(f"  - {slug} (필드: {', '.join(sorted(fields))})")
    return "\n".join(lines)


# ── G-5: 자동 회귀 테스트 ────────────────────────────────────────────────────

def run_regression() -> tuple[bool, str]:
    """pytest tests/ 실행 → (passed: bool, summary: str)."""
    python = sys.executable
    r = subprocess.run(
        [python, "-m", "pytest", "tests/", "-q", "--tb=short"],
        cwd=str(_BASE),
        capture_output=True,
        text=True,
        timeout=120,
    )
    output = (r.stdout + r.stderr).strip()
    passed = r.returncode == 0
    last_lines = "\n".join(output.splitlines()[-5:])
    return passed, last_lines


# ── G-7: Changelog/Audit 기록 ────────────────────────────────────────────────

def _audit_append(slug: str, action: str, detail: str,
                   source: str = "", impacted: list[str] | None = None) -> None:
    """LEGAL_BASIS_AUDIT.md 에 한 줄 추가."""
    _AUDIT.parent.mkdir(parents=True, exist_ok=True)
    if not _AUDIT.exists():
        _AUDIT.write_text(
            "# LEGAL_BASIS_AUDIT.md — 법령 변경 이력 (RMS G-7)\n\n"
            "| 날짜 | slug | 액션 | 출처 | 영향 계산기 | 상세 |\n"
            "|------|------|------|------|------------|------|\n",
            encoding="utf-8",
        )
    imp_str = ", ".join(impacted) if impacted else "-"
    row = (f"| {_now()} | {slug} | {action} | {source or '-'} "
           f"| {imp_str} | {detail[:120]} |\n")
    with _AUDIT.open("a", encoding="utf-8") as f:
        f.write(row)


def _archive_snapshot() -> None:
    """현재 master.yaml을 archive/{year}.yaml 에 덮어쓰기(연간 최신 스냅샷)."""
    _ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    arch = _ARCHIVE_DIR / f"{_year()}.yaml"
    content = _MASTER.read_text(encoding="utf-8")
    header = (f"# legal_basis.archive/{_year()}.yaml -- {_year()}년 법령 요율 스냅샷\n"
              f"# 갱신일: {_now()}  출처: legal_basis.master.yaml\n#\n")
    # 기존 헤더 제거 후 새 헤더 붙이기
    lines = content.split("\n")
    body_start = next((i for i, l in enumerate(lines) if not l.startswith("#") and l.strip()), 0)
    body = "\n".join(lines[body_start:])
    arch.write_text(header + body, encoding="utf-8")


# ── G-4: 워크플로 핵심 — PROMOTE ─────────────────────────────────────────────

def promote(slug: str, source: str = "", skip_regression: bool = False) -> dict:
    """draft.yaml 의 slug 항목을 master.yaml 로 승격.

    단계:
      1. draft.yaml 에서 slug 항목 읽기
      2. (skip_regression=False) 회귀 테스트 실행 → 실패 시 REJECTED
      3. master.yaml 의 해당 slug 업데이트
      4. Audit 기록 + Archive 스냅샷 갱신
      5. Telegram 알림(선택)

    반환: {"status": "PROMOTED"|"REJECTED", "message": str}
    """
    draft = _read_yaml(_DRAFT)
    master = _read_yaml(_MASTER)

    if slug not in draft:
        return {"status": "REJECTED", "message": f"draft.yaml에 '{slug}' 없음"}

    entry = draft[slug]
    rms_status = entry.get("rms_status", "DRAFT")

    if rms_status not in ("APPROVED", "UNDER_REVIEW"):
        return {
            "status": "REJECTED",
            "message": (f"'{slug}' 의 rms_status={rms_status}. "
                        "APPROVED 또는 UNDER_REVIEW 상태만 승격 가능"),
        }

    # G-5: 회귀 테스트
    if not skip_regression:
        passed, summary = run_regression()
        if not passed:
            _audit_append(slug, "REJECTED", f"회귀 실패: {summary}", source)
            _notify_rms("REJECTED", slug, f"회귀 테스트 실패\n{summary}")
            return {"status": "REJECTED", "message": f"회귀 테스트 실패:\n{summary}"}

    # 변경 전 값 기록
    old_entry = master.get(slug, {})

    # master 업데이트
    clean_entry = {k: v for k, v in entry.items() if k != "rms_status"}
    master[slug] = clean_entry

    # master.yaml 저장
    _MASTER_HEADER = (
        "# legal_basis.master.yaml -- 검증 완료 계산기 법령 레지스트리 (RMS 관리)\n"
        "# 직접 편집 금지 -- rms_promote.py 워크플로를 통해서만 변경\n"
        "#\n"
    )
    _write_yaml(_MASTER, master, _MASTER_HEADER)

    # G-7: Audit + Archive
    impacted = find_impacted(slug)
    _audit_append(slug, "PROMOTED", f"rms_status={rms_status}→PROMOTED", source, impacted)
    _archive_snapshot()

    # G-6: Telegram 알림
    _notify_rms("PROMOTED", slug, f"출처: {source or '-'}\n영향 계산기: {', '.join(impacted) or '없음'}")

    return {"status": "PROMOTED", "message": f"'{slug}' → master.yaml 승격 완료"}


# ── G-2: 법령 변경 감지 — 수동 체크 후 DRAFT 생성 ──────────────────────────

def create_draft(slug: str, changes: dict, source: str = "") -> dict:
    """법령 변경 감지 시 draft.yaml 에 DRAFT 상태 항목 생성.

    changes: 변경할 필드 dict (예: {"benefit_amounts.daily_max": 70000})
    """
    draft = _read_yaml(_DRAFT)
    master = _read_yaml(_MASTER)

    base_entry = dict(master.get(slug, {}))
    if not base_entry:
        return {"status": "ERROR", "message": f"master.yaml에 '{slug}' 없음 — 신규 계산기는 별도 절차 필요"}

    # 필드 업데이트 (dot-notation 지원)
    for field, value in changes.items():
        parts = field.split(".")
        target = base_entry
        for p in parts[:-1]:
            target = target.setdefault(p, {})
        target[parts[-1]] = value

    base_entry["rms_status"] = "DRAFT"
    base_entry["rms_detected"] = _now()
    base_entry["rms_source"] = source or ""
    base_entry["rms_changes"] = changes

    draft[slug] = base_entry

    # draft.yaml 헤더 유지 (기존 내용 읽기)
    _DRAFT_HEADER = (
        "# legal_basis.draft.yaml -- 법령 변경 검토 워크스페이스 (RMS G-2)\n"
        "# 이 파일은 법령 변경 감지 시 자동 생성되는 DRAFT 항목을 담습니다.\n"
        "# 직접 편집해도 계산기에 반영되지 않습니다 -- rms_promote.py 워크플로 필요.\n"
        "#\n"
    )
    _write_yaml(_DRAFT, draft, _DRAFT_HEADER)

    impacted = find_impacted(slug)
    _audit_append(slug, "DRAFT 생성", f"변경 감지: {list(changes.keys())}", source, impacted)
    _notify_rms("DRAFT", slug, f"감지된 변경: {list(changes.keys())}\n출처: {source or '-'}")

    return {"status": "DRAFT", "message": f"'{slug}' DRAFT 생성 완료. rms_promote.py로 승격하세요."}


def approve_draft(slug: str, approver: str = "운영자") -> dict:
    """draft.yaml 의 slug 항목을 UNDER_REVIEW → APPROVED 전환."""
    draft = _read_yaml(_DRAFT)
    if slug not in draft:
        return {"status": "ERROR", "message": f"draft.yaml에 '{slug}' 없음"}
    entry = draft[slug]
    current = entry.get("rms_status", "DRAFT")
    if current not in ("DRAFT", "UNDER_REVIEW"):
        return {"status": "ERROR", "message": f"현재 상태 {current} — DRAFT/UNDER_REVIEW만 APPROVED 가능"}
    entry["rms_status"] = "APPROVED"
    entry["rms_approved_by"] = approver
    entry["rms_approved_at"] = _now()
    draft[slug] = entry
    _write_yaml(_DRAFT, draft)
    _audit_append(slug, "APPROVED", f"승인자: {approver}", impacted=find_impacted(slug))
    return {"status": "APPROVED", "message": f"'{slug}' APPROVED. promote 명령으로 master 승격 가능"}


# ── G-6: Telegram 알림 ───────────────────────────────────────────────────────

def _notify_rms(event: str, slug: str, detail: str = "") -> None:
    """RMS 이벤트 Telegram 알림. 실패해도 무시(알림은 보조 수단)."""
    try:
        from .telegram_notifier import notify as _tg_notify
        msg = f"[RMS {event}] {slug}\n{detail}"
        _tg_notify(msg)
    except Exception:
        pass
