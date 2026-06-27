# -*- coding: utf-8 -*-
"""
modules/scheduler.py — 글별 발행 시간 슬롯 스케줄러 (v12 신규)

운영자가 DAILY_POST_COUNT 만큼 슬롯(시작~종료 시간 범위)을 지정하면,
당일 시작 시 각 슬롯 범위 내 랜덤 시각을 1회 생성하여 하루 동안 고정한다.
현재 시각이 예약 시각에 도달하면 해당 글 1건만 발행한다.

영속: data/schedule/today_schedule.json (프로그램 재시작 후에도 유지)
이력: data/schedule/history.jsonl  (예약/실제/지연/결과 — 운영로그 확장)

config.yaml 의 PUBLISH_SCHEDULE 로 슬롯을 설정한다(대시보드에서 편집):
    PUBLISH_SCHEDULE:
      enabled: true
      failure_mode: retry_in_slot   # none | retry_in_slot | next_slot
      weekday:
        - {start: "07:00", end: "08:00"}
        - {start: "12:00", end: "13:00"}
      weekend:
        - {start: "09:00", end: "10:00"}
슬롯 미설정 시 DAILY_POST_COUNT 만큼 09~21시 사이로 균등 자동 생성.
"""
import json
import random
import time
from datetime import datetime, date, timedelta
from pathlib import Path

from .logger import get_logger

LOG = get_logger()

FAILURE_MODES = ("none", "retry_in_slot", "next_slot")
STATUSES = ("pending", "running", "completed", "failed", "retry")


# ── 경로 ──────────────────────────────────────────────────────────
def _schedule_dir(cfg: dict) -> Path:
    root = Path(cfg.get("_root", "."))
    d = root / "data" / "schedule"
    d.mkdir(parents=True, exist_ok=True)
    return d

def _schedule_path(cfg: dict) -> Path:
    return _schedule_dir(cfg) / "today_schedule.json"

def _history_path(cfg: dict) -> Path:
    return _schedule_dir(cfg) / "history.jsonl"

def _lock_path(cfg: dict) -> Path:
    return _schedule_dir(cfg) / "scheduler.lock"


# ── 시간 유틸 ─────────────────────────────────────────────────────
def _to_min(hhmm: str) -> int:
    h, m = hhmm.strip().split(":")
    return int(h) * 60 + int(m)

def _to_hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"

def _is_weekend(d: date) -> bool:
    return d.weekday() >= 5   # 5=토, 6=일


# ── 슬롯 설정 ─────────────────────────────────────────────────────
def default_slots(count: int) -> list:
    """09:00~21:00 사이를 count개 1시간 슬롯으로 균등 분할."""
    count = max(1, int(count or 1))
    start_min, end_min = 9 * 60, 21 * 60
    span = end_min - start_min
    step = span // count
    slots = []
    for i in range(count):
        s = start_min + i * step
        e = min(s + min(step, 60), end_min)
        if e <= s:
            e = s + 30
        slots.append({"start": _to_hhmm(s), "end": _to_hhmm(e)})
    return slots

def get_slots_for(cfg: dict, d: date = None) -> tuple:
    """(day_type, slots) 반환. PUBLISH_SCHEDULE 우선, 없으면 자동 생성."""
    d = d or date.today()
    day_type = "weekend" if _is_weekend(d) else "weekday"
    ps = cfg.get("PUBLISH_SCHEDULE", {}) or {}
    slots = ps.get(day_type) or []
    if not slots:
        count = int(cfg.get("DAILY_POST_COUNT", 1) or 1)
        slots = default_slots(count)
    return day_type, slots

def failure_mode(cfg: dict) -> str:
    ps = cfg.get("PUBLISH_SCHEDULE", {}) or {}
    fm = ps.get("failure_mode", "retry_in_slot")
    return fm if fm in FAILURE_MODES else "retry_in_slot"


# ── 검증 ──────────────────────────────────────────────────────────
def validate_slots(slots: list, expected_count: int = None) -> list:
    """슬롯 설정 검증. 오류 메시지 리스트 반환(빈 리스트면 정상)."""
    errors = []
    if not slots:
        return ["슬롯이 비어 있습니다."]
    if expected_count is not None and len(slots) != expected_count:
        errors.append(f"슬롯 수({len(slots)})가 DAILY_POST_COUNT({expected_count})와 다릅니다.")
    ranges = []
    for i, s in enumerate(slots, 1):
        st, en = s.get("start", ""), s.get("end", "")
        try:
            sm, em = _to_min(st), _to_min(en)
        except Exception:
            errors.append(f"글{i}: 시간 형식 오류 (HH:MM) — start={st!r}, end={en!r}")
            continue
        if not (0 <= sm < 24 * 60 and 0 <= em <= 24 * 60):
            errors.append(f"글{i}: 시간 범위 초과 — {st}~{en}")
        if sm >= em:
            errors.append(f"글{i}: 시작시간이 종료시간 이상입니다 — {st} >= {en}")
        ranges.append((sm, em, i))
    # 슬롯 중복(겹침) 경고
    ranges.sort()
    for a, b in zip(ranges, ranges[1:]):
        if a[1] > b[0]:
            errors.append(f"슬롯 겹침 경고: 글{a[2]}({_to_hhmm(a[0])}~{_to_hhmm(a[1])}) ↔ "
                          f"글{b[2]}({_to_hhmm(b[0])}~{_to_hhmm(b[1])})")
    return errors


# ── 스케줄 생성/저장/로드 ─────────────────────────────────────────
def _rand_time_in(start: str, end: str, taken: set) -> str:
    """[start, end) 내 랜덤 HH:MM, 이미 사용된 시각과 중복 방지."""
    sm, em = _to_min(start), _to_min(end)
    if em <= sm:
        em = sm + 1
    for _ in range(50):
        t = random.randint(sm, max(sm, em - 1))
        if t not in taken:
            taken.add(t)
            return _to_hhmm(t)
    taken.add(sm)
    return _to_hhmm(sm)

def generate_today_schedule(cfg: dict, d: date = None) -> dict:
    """오늘(또는 지정일) 스케줄 생성 후 저장."""
    d = d or date.today()
    day_type, slots = get_slots_for(cfg, d)
    taken = set()
    entries = []
    for i, slot in enumerate(slots, 1):
        st, en = slot.get("start", "09:00"), slot.get("end", "10:00")
        try:
            sched_time = _rand_time_in(st, en, taken)
        except Exception:
            sched_time = st
        entries.append({
            "post_no": i,
            "slot_start": st,
            "slot_end": en,
            "scheduled_time": sched_time,
            "status": "pending",
            "actual_time": "",
            "delay_min": "",
            "result": "",
            "attempts": 0,
        })
    entries.sort(key=lambda e: e["scheduled_time"])
    sched = {
        "date": d.isoformat(),
        "day_type": day_type,
        "failure_mode": failure_mode(cfg),
        "schedule": entries,
    }
    save_schedule(cfg, sched)
    LOG.info("오늘(%s, %s) 발행 일정 생성: %d건", d.isoformat(), day_type, len(entries))
    return sched

def load_schedule(cfg: dict) -> dict | None:
    p = _schedule_path(cfg)
    if not p.exists():
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        LOG.warning("today_schedule.json 로드 실패: %s", e)
        return None

def save_schedule(cfg: dict, sched: dict):
    with open(_schedule_path(cfg), "w", encoding="utf-8") as f:
        json.dump(sched, f, ensure_ascii=False, indent=2)

def ensure_today_schedule(cfg: dict) -> dict:
    """오늘 일정이 없거나 날짜가 바뀌었으면 새로 생성(다음날 자동 생성)."""
    sched = load_schedule(cfg)
    today = date.today().isoformat()
    if sched is None or sched.get("date") != today:
        sched = generate_today_schedule(cfg)
    return sched

def reset_today(cfg: dict):
    """오늘 일정 초기화(삭제)."""
    _schedule_path(cfg).unlink(missing_ok=True)
    LOG.info("오늘 일정 초기화 완료")


# ── 실행 ──────────────────────────────────────────────────────────
def get_due_posts(sched: dict, now: datetime = None) -> list:
    """현재 시각 이상이고 아직 실행 대기(pending/retry)인 글 목록."""
    now = now or datetime.now()
    now_min = now.hour * 60 + now.minute
    due = []
    for e in sched.get("schedule", []):
        if e.get("status") in ("pending", "retry"):
            try:
                if _to_min(e["scheduled_time"]) <= now_min:
                    due.append(e)
            except Exception:
                continue
    return due

def _append_history(cfg: dict, sched: dict, entry: dict):
    rec = {
        "date": sched.get("date"),
        "post_no": entry.get("post_no"),
        "scheduled_time": entry.get("scheduled_time"),
        "actual_time": entry.get("actual_time"),
        "delay_min": entry.get("delay_min"),
        "status": entry.get("status"),
        "result": entry.get("result"),
        "attempts": entry.get("attempts"),
    }
    try:
        with open(_history_path(cfg), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as e:
        LOG.warning("스케줄 이력 기록 실패: %s", e)

def _apply_failure_mode(cfg: dict, sched: dict, entry: dict):
    """실패 시 모드별 후처리."""
    mode = sched.get("failure_mode", "retry_in_slot")
    now_min = datetime.now().hour * 60 + datetime.now().minute
    if mode == "none":
        entry["status"] = "failed"
        LOG.info("글%s 실패 — 재시도 안함(mode=none)", entry["post_no"])
    elif mode == "retry_in_slot":
        end_min = _to_min(entry["slot_end"])
        if now_min < end_min - 1:
            new_t = _rand_time_in(_to_hhmm(now_min + 1), entry["slot_end"], set())
            entry["scheduled_time"] = new_t
            entry["status"] = "retry"
            LOG.info("글%s 실패 — 슬롯 내 재예약 %s", entry["post_no"], new_t)
        else:
            entry["status"] = "failed"
            LOG.info("글%s 실패 — 슬롯 시간 소진, 재시도 불가", entry["post_no"])
    elif mode == "next_slot":
        # 다음 빈(pending/retry) 슬롯 시각으로 이동
        later = [e for e in sched["schedule"]
                 if e["post_no"] != entry["post_no"]
                 and e["status"] in ("pending", "retry")
                 and _to_min(e["scheduled_time"]) > now_min]
        if later:
            target = min(later, key=lambda e: _to_min(e["scheduled_time"]))
            entry["scheduled_time"] = target["scheduled_time"]
            entry["status"] = "retry"
            LOG.info("글%s 실패 — 다음 슬롯(%s)으로 이동", entry["post_no"], target["scheduled_time"])
        else:
            entry["status"] = "failed"
            LOG.info("글%s 실패 — 다음 빈 슬롯 없음", entry["post_no"])

def execute_due_post(cfg: dict, sched: dict, entry: dict, run_once_fn) -> str:
    """예약 도래한 글 1건 실행. run_once_fn(cfg, max_count=1) 사용."""
    now = datetime.now()
    entry["status"] = "running"
    entry["attempts"] = int(entry.get("attempts", 0)) + 1
    entry["actual_time"] = now.strftime("%H:%M")
    try:
        delay = (now.hour * 60 + now.minute) - _to_min(entry["scheduled_time"])
        entry["delay_min"] = max(0, delay)
    except Exception:
        entry["delay_min"] = ""
    save_schedule(cfg, sched)
    LOG.info("▶ 글%s 발행 실행 (예약 %s / 실제 %s)",
             entry["post_no"], entry["scheduled_time"], entry["actual_time"])
    try:
        stats = run_once_fn(cfg, max_count=1) or {}
        produced = stats.get("produced", 0) if isinstance(stats, dict) else 0
        if produced >= 1:
            entry["status"] = "completed"
            entry["result"] = "성공"
            LOG.info("✅ 글%s 발행 완료", entry["post_no"])
        else:
            entry["result"] = f"미생산({stats.get('reason','')})"
            _apply_failure_mode(cfg, sched, entry)
    except Exception as e:
        entry["result"] = f"오류:{str(e)[:80]}"
        LOG.error("글%s 실행 오류: %s", entry["post_no"], e, exc_info=True)
        _apply_failure_mode(cfg, sched, entry)
    save_schedule(cfg, sched)
    _append_history(cfg, sched, entry)
    return entry["status"]


def summarize(sched: dict) -> dict:
    """오늘 일정 요약(빠른 KPI용)."""
    items = (sched or {}).get("schedule", [])
    from collections import Counter
    c = Counter(e.get("status") for e in items)
    nxt = None
    pend = sorted([e for e in items if e.get("status") in ("pending", "retry")],
                  key=lambda x: x.get("scheduled_time", ""))
    if pend:
        nxt = pend[0].get("scheduled_time")
    return {
        "total": len(items),
        "completed": c.get("completed", 0),
        "pending": c.get("pending", 0) + c.get("retry", 0),
        "failed": c.get("failed", 0),
        "running": c.get("running", 0),
        "next": nxt,
    }


def immediate_publish(cfg: dict, run_once_fn, mode: str = "pull") -> tuple:
    """예약시간 무시하고 즉시 1건 발행.

    mode="pull": 다음 대기 슬롯 1개를 당겨서 소모(기본).
    mode="add" : 슬롯 소모 없이 추가 발행(오늘 일정에 '즉시' 항목 추가).
    반환: (ok, message)
    """
    sched = ensure_today_schedule(cfg)
    now = datetime.now()
    if not _acquire_lock(cfg):
        return False, "다른 발행이 진행 중입니다(lock). 잠시 후 다시 시도하세요."
    try:
        try:
            stats = run_once_fn(cfg, max_count=1) or {}
        except Exception as e:
            LOG.error("즉시 발행 실행 오류: %s", e, exc_info=True)
            return False, f"즉시 발행 실패: {e}"
        produced = stats.get("produced", 0) if isinstance(stats, dict) else 0
        result = "성공" if produced >= 1 else f"미생산({stats.get('reason','')})"

        target = None
        if mode == "pull":
            pend = sorted([e for e in sched["schedule"] if e.get("status") in ("pending", "retry")],
                          key=lambda x: _to_min(x["scheduled_time"]) if ":" in str(x.get("scheduled_time","")) else 9999)
            target = pend[0] if pend else None

        if target is not None:   # 당겨쓰기
            target["status"] = "completed" if produced >= 1 else "failed"
            target["actual_time"] = now.strftime("%H:%M")
            target["result"] = f"즉시({result})"
            target["attempts"] = int(target.get("attempts", 0)) + 1
            target["delay_min"] = 0
            _append_history(cfg, sched, {**target, "scheduled_time": "즉시실행"})
        else:                    # 추가 발행
            post_no = max([e.get("post_no", 0) for e in sched["schedule"]] or [0]) + 1
            entry = {
                "post_no": post_no, "slot_start": "-", "slot_end": "-",
                "scheduled_time": "즉시실행",
                "status": "completed" if produced >= 1 else "failed",
                "actual_time": now.strftime("%H:%M"), "delay_min": 0,
                "result": result, "attempts": 1,
            }
            sched["schedule"].append(entry)
            _append_history(cfg, sched, entry)
        save_schedule(cfg, sched)
        LOG.info("즉시 발행(%s): %s", mode, result)
        return (produced >= 1), f"즉시 발행 {result}"
    finally:
        _release_lock(cfg)


def run_scheduler_loop(cfg: dict, run_once_fn, poll_seconds: int = 30):
    """슬롯 스케줄러 메인 루프. 수동 실행과의 동시 실행 방지를 위해 lock 사용."""
    LOG.info("슬롯 발행 스케줄러 시작 (poll=%ds)", poll_seconds)
    while True:
        try:
            # 비용 관리: 80% 경고 / 100% 자동 일시정지(익일 자동 재개)
            try:
                from . import cost_manager
                cost_manager.check_budget_alerts(cfg)
                if cost_manager.is_paused(cfg):
                    LOG.warning("[cost] 일 예산 한도 — 발행 일시정지(익일 재개). 이번 주기 건너뜀")
                    time.sleep(poll_seconds)
                    continue
            except Exception as _e:
                LOG.warning("cost_manager 점검 실패(무시): %s", _e)
            sched = ensure_today_schedule(cfg)
            for entry in get_due_posts(sched):
                if _acquire_lock(cfg):
                    try:
                        execute_due_post(cfg, sched, entry, run_once_fn)
                    finally:
                        _release_lock(cfg)
                else:
                    LOG.info("다른 실행이 진행 중(lock) — 이번 주기 건너뜀")
                    break
            remaining = [e for e in sched["schedule"] if e["status"] in ("pending", "retry")]
            if not remaining:
                LOG.info("오늘 일정 모두 처리됨 — 다음 날 자동 생성 대기")
        except Exception as e:
            LOG.error("스케줄러 루프 오류: %s", e, exc_info=True)
        time.sleep(poll_seconds)


# ── 수동 실행 충돌 방지용 단순 파일 락 ────────────────────────────
def _acquire_lock(cfg: dict, stale_seconds: int = 1800) -> bool:
    p = _lock_path(cfg)
    if p.exists():
        try:
            if time.time() - p.stat().st_mtime > stale_seconds:
                p.unlink(missing_ok=True)  # stale lock 제거
            else:
                return False
        except Exception:
            return False
    try:
        p.write_text(datetime.now().isoformat(), encoding="utf-8")
        return True
    except Exception:
        return False

def _release_lock(cfg: dict):
    _lock_path(cfg).unlink(missing_ok=True)
