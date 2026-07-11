# -*- coding: utf-8 -*-
"""
modules/cost_manager.py — 일일 비용 관리 (v12 Lite, 신규)

- 일일 비용 집계(BudgetTracker 재사용)
- 80% 도달 → 텔레그램 경고(1일 1회)
- 100% 도달 → 자동 일시정지(상태 파일) + 텔레그램
- 다음날 자동 재개(날짜 바뀌면 pause 해제)

상태: data/logs/cost_state.json {paused_date, warned_date}
기존 파이프라인(run_once)의 예산 선차단은 그대로 유지. 본 모듈은 '경고+영속 일시정지'를 추가.
"""
import json
from datetime import date
from pathlib import Path

from .logger import BudgetTracker, get_logger
from . import telegram_ops as TG

LOG = get_logger()
_STATE = Path(__file__).resolve().parent.parent / "data" / "logs" / "cost_state.json"


def _load() -> dict:
    if _STATE.exists():
        try:
            return json.loads(_STATE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save(d: dict):
    _STATE.parent.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def status(cfg: dict) -> dict:
    bt = BudgetTracker(cfg)
    bs = bt.check_budget()
    used, limit = bs["daily_used"], bs["daily_limit"] or 1
    pct = used / limit * 100
    return {"used": used, "limit": limit, "pct": round(pct, 1),
            "daily_exceeded": bs["daily_exceeded"], "monthly_exceeded": bs["monthly_exceeded"]}


def is_paused(cfg: dict) -> bool:
    """오늘 자동 일시정지 상태인지. 날짜가 바뀌면 자동 해제(익일 재개)."""
    st = _load()
    return st.get("paused_date") == date.today().isoformat()


def check_budget_alerts(cfg: dict) -> dict:
    """예산 점검 → 80% 경고 / 100% 일시정지(텔레그램). 반환: status + actions."""
    s = status(cfg)
    st = _load()
    today = date.today().isoformat()
    actions = []

    # 100% → 일시정지
    if s["pct"] >= 100 or s["daily_exceeded"]:
        if st.get("paused_date") != today:
            st["paused_date"] = today
            _save(st)
            TG.notify_budget(cfg, s["used"], s["limit"], "stop")
            LOG.warning("[cost] 일 예산 100%% — 자동 일시정지(%s)", today)
            actions.append("paused")
    # 80% → 경고(1일 1회)
    elif s["pct"] >= 80:
        if st.get("warned_date") != today:
            st["warned_date"] = today
            _save(st)
            TG.notify_budget(cfg, s["used"], s["limit"], "warn")
            LOG.info("[cost] 일 예산 80%% 경고(%s)", today)
            actions.append("warned")

    s["paused"] = is_paused(cfg)
    s["actions"] = actions
    return s


def pause(cfg: dict):
    """수동 일시정지(운영자 중지). is_paused/resume과 같은 상태(paused_date)를 재사용하므로
    run_scheduler_loop이 기존 is_paused 체크로 발행을 건너뛴다(scheduler 로직 무변경).
    ※ 날짜가 바뀌면 is_paused가 자동 해제(익일 재개) — 예산 일시정지와 동일 정책."""
    st = _load()
    st["paused_date"] = date.today().isoformat()
    _save(st)
    LOG.info("[cost] 수동 일시정지(중지)")


def resume(cfg: dict):
    """수동 재개(일시정지 해제)."""
    st = _load()
    st.pop("paused_date", None)
    _save(st)
    LOG.info("[cost] 수동 재개")
