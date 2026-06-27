# -*- coding: utf-8 -*-
"""
modules/site_mode_manager.py — 사이트 운영 모드 관리 (SalaryMate)

config/site_mode.yaml 기반. 모드별 광고/CPA/공유/리포트/관련계산기 노출 정책 제공.
템플릿 렌더링 시 이 플래그로 섹션 표시 여부 결정.
"""
from pathlib import Path

import yaml

from .logger import get_logger

LOG = get_logger()
_PATH = Path(__file__).resolve().parent.parent / "config" / "site_mode.yaml"

_DEFAULT_MODES = {
    "pre_adsense":  {"ads": False, "cpa": False, "share": False, "report": False, "related": False},
    "post_adsense": {"ads": True,  "cpa": False, "share": False, "report": False, "related": True},
    "growth":       {"ads": True,  "cpa": True,  "share": True,  "report": True,  "related": True},
}


def _load() -> dict:
    try:
        return yaml.safe_load(_PATH.read_text(encoding="utf-8")) or {}
    except Exception as e:
        LOG.warning("site_mode.yaml 로드 실패→기본(pre_adsense): %s", e)
        return {}


def get_mode() -> str:
    m = _load().get("mode", "pre_adsense")
    return m if m in _DEFAULT_MODES else "pre_adsense"


def _flags(mode: str = None) -> dict:
    data = _load()
    mode = mode or data.get("mode", "pre_adsense")
    modes = data.get("modes", {}) or {}
    return modes.get(mode) or _DEFAULT_MODES.get(mode, _DEFAULT_MODES["pre_adsense"])


def set_mode(mode: str) -> bool:
    """모드 변경 후 저장. 유효 모드만."""
    if mode not in _DEFAULT_MODES:
        return False
    data = _load() or {}
    data["mode"] = mode
    data.setdefault("modes", _DEFAULT_MODES)
    _PATH.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    LOG.info("site_mode 변경: %s", mode)
    return True


def is_ads_enabled() -> bool:    return bool(_flags().get("ads"))
def is_cpa_enabled() -> bool:    return bool(_flags().get("cpa"))
def is_share_enabled() -> bool:  return bool(_flags().get("share"))
def is_report_enabled() -> bool: return bool(_flags().get("report"))
def is_related_enabled() -> bool: return bool(_flags().get("related"))


def all_flags() -> dict:
    return {"mode": get_mode(), **_flags()}
