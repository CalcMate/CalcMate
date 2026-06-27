# -*- coding: utf-8 -*-
"""
modules/pipeline_status.py — AI 파이프라인 단계 상태 (v12.0)

기존 파이프라인(main._process_one)을 수정하지 않고, pipeline.log 의 STEP 마커를
파싱해 단계별 상태를 재구성한다(비침습적). 비용/토큰은 budget.json에서 읽는다.

상태: pending(노랑) / running(파랑) / completed(초록) / error(빨강)
"""
from pathlib import Path

from .logger import BudgetTracker, get_logger

LOG = get_logger()

LOG_PATH = Path(__file__).resolve().parent.parent / "data" / "logs" / "pipeline.log"

# 단계 정의: (이름, 완료 판정 마커, 모델 표기 cfg 키 또는 고정문구)
STAGES = [
    {"name": "키워드 수집", "done": "STEP 1 완료", "start": "STEP 1", "model": "RSS/Collector"},
    {"name": "리서치/전략", "done": "STEP 6 완료", "start": "STEP 5", "model_key": "MODEL_PLANNER"},
    {"name": "본문 작성",   "done": "STEP 7 완료", "start": "STEP 7", "model_key": "MODEL_WRITER"},
    {"name": "검수",        "done": "STEP 8 완료", "start": "STEP 8", "model_key": "MODEL_EDITOR"},
    {"name": "이미지 생성", "done": "STEP 11",     "start": "STEP 10", "model": "Pollinations"},
    {"name": "발행",        "done": "STEP 11 완료", "start": "STEP 11", "model": "WordPress REST"},
]


def _tail(n: int = 400, blk: int = 131072) -> list:
    """로그 끝부분 바이트만 읽어 마지막 n줄 반환(전체 읽기 금지)."""
    if not LOG_PATH.exists():
        return []
    try:
        sz = LOG_PATH.stat().st_size
        with open(LOG_PATH, "rb") as f:
            f.seek(max(0, sz - blk))
            data = f.read()
        return data.decode("utf-8", "replace").splitlines()[-n:]
    except Exception:
        return []


def get_pipeline_state(cfg: dict) -> dict:
    lines = _tail()
    # 마지막 실행 구간: 마지막 'STEP 1 시작' 이후
    start_idx = 0
    for i in range(len(lines) - 1, -1, -1):
        if "STEP 1: 수집 시작" in lines[i] or "항목 처리" in lines[i]:
            start_idx = i
            break
    segment = lines[start_idx:]
    seg_text = "\n".join(segment)
    finished = ("실행 종료" in seg_text) or ("항목 완료" in seg_text)
    has_error = any("[ERROR]" in l for l in segment)

    stages = []
    current_found = False
    for s in STAGES:
        model = s.get("model") or cfg.get(s.get("model_key", ""), "-")
        done = s["done"] in seg_text
        started = s["start"] in seg_text
        if done:
            status = "completed"
        elif started and not current_found and not finished:
            status = "running"; current_found = True
        else:
            status = "pending"
        stages.append({"name": s["name"], "model": model, "status": status})

    if has_error and not finished:
        # 진행 중 오류면 현재 단계를 error로
        for st in stages:
            if st["status"] == "running":
                st["status"] = "error"
                break
        else:
            stages[-1]["status"] = "error" if not stages[-1]["status"] == "completed" else stages[-1]["status"]

    # 비용/토큰 (오늘)
    cost_today = tok_today = 0
    model_costs = {}
    try:
        bt = BudgetTracker(cfg)
        cost_today = round(bt.get_daily_cost(), 4)
        tok_today = int(bt.get_today_tokens())
        model_costs = bt.get_model_breakdown("daily")
    except Exception as _e:
        LOG.warning("토큰 비용 기록/조회 실패: %s", _e)

    return {
        "stages": stages,
        "finished": finished,
        "has_error": has_error,
        "cost_today": cost_today,
        "tokens_today": tok_today,
        "model_costs": model_costs,
        "last_lines": segment[-12:],
    }
