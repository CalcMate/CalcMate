# -*- coding: utf-8 -*-
"""
Phase B 검증 -- collect_rewrite_candidates() 후보 선정 로직
검증 항목:
  B-01. RMS rate_changed(HIGH) -> 포함
  B-02. RMS wording_changed(LOW) -> severity 미달 제외
  B-03. RMS 이미 processed -> SKIP
  B-04. RMS IMPACT_MAP 없는 entity -> 제외
  B-05. time-based 365+일 경과, 쿨다운 없음 -> 포함
  B-06. time-based 365+일 경과, 쿨다운 30일(90일 미만) -> 제외
  B-07. time-based 100일 경과(stale 미달) -> 제외
  B-08. 동일 계산기 RMS+time-based -> RMS(높은 severity) 채택
  B-09. DAILY_REWRITE_LIMIT=1 -> 최대 1건
  B-10. 리라이트중 상태 article -> 제외
  B-11. 후보 구조 -- 필수 필드 누락 없음
  B-12. collect_rewrite_candidates 가 update_post 미호출
  B-13. 후보 0건 -- 오류 없이 [] 반환
  B-14. reason 필수 필드 -- type/source/detected_at/severity
  B-15. RMS 후보 -- rms_event_id 존재
"""
import gc
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASS_STR = "[PASS]"
FAIL_STR = "[FAIL]"
errors = []


def check(name: str, cond: bool, detail: str = ""):
    if cond:
        print(f"{PASS_STR} {name}")
    else:
        msg = f"{FAIL_STR} {name}" + (f" -- {detail}" if detail else "")
        print(msg)
        errors.append(msg)


# ── 단일 Temp 디렉터리 (Windows SQLite 잠금 회피) ────────────────────────────
TMPDIR = tempfile.mkdtemp(prefix="rewrite_b_")


def make_cfg(subdir: str, limit: int = 1) -> dict:
    """각 시나리오마다 별도 서브디렉터리를 사용해 DB 격리."""
    root = os.path.join(TMPDIR, subdir)
    os.makedirs(root, exist_ok=True)
    return {
        "_root": root,
        "DB_ADAPTER": "sqlite",
        "SQLITE_PATH": "data/test_rewrite.db",
        "REWRITE_STALE_DAYS": 365,
        "REWRITE_COOLDOWN_DAYS": 90,
        "REWRITE_CHANGE_SEVERITY_MIN": "MEDIUM",
        "DAILY_REWRITE_LIMIT": limit,
    }


def get_repos(cfg: dict):
    from adapters.db.factory import get_db_adapter
    from repositories.article_repository import ArticleRepository
    from repositories.calculator_repository import CalculatorRepository
    db = get_db_adapter(cfg)
    return ArticleRepository(db), CalculatorRepository(db), db


def insert_calc(db, calc_id: str, slug: str, name: str) -> str:
    db.insert("calculators", {
        "id": calc_id, "slug": slug, "name": name, "status": "active",
    })
    return calc_id


def insert_article(db, article_id: str, cid: str, wp_post_id: str,
                   published_at: str, status: str = "발행완료",
                   history: list = None) -> str:
    db.insert("articles", {
        "ID": article_id,
        "calculator_id": cid,
        "상태값": status,
        "wp_post_id": wp_post_id,
        "published_at": published_at,
        "정책명": "테스트정책",
        "history": json.dumps(history or []),
    })
    return article_id


def write_revision_state(cfg: dict, state: dict):
    p = Path(cfg["_root"]) / "data" / "legal" / "revision_state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def days_ago(n: int) -> str:
    return (datetime.now() - timedelta(days=n)).isoformat()


def rewrite_success_event(days: int) -> dict:
    return {"event": "rewrite_success", "ts": days_ago(days)}


# ── B-01~B-04: RMS 후보 시나리오 ─────────────────────────────────────────────

print("\n[RMS 시나리오]")

# B-01: rate_changed(HIGH) -> 포함
cfg = make_cfg("b01")
_, _, db = get_repos(cfg)
insert_calc(db, "c-wage-001", "weekly-holiday-allowance", "주휴수당 계산기")
insert_calc(db, "c-unemp-001", "unemployment-benefit", "구직급여 계산기")
insert_article(db, "art-wage-001", "c-wage-001", "wp-100", days_ago(200))
insert_article(db, "art-unemp-001", "c-unemp-001", "wp-200", days_ago(300))
write_revision_state(cfg, {
    "min_wage_hourly": {"source_hash": "abc", "last_changed": "2026-08-01",
                        "change_type": ["rate_changed"]}
})
from modules.rewrite_pipeline import _rms_candidates
c01 = _rms_candidates(cfg, {})
check("B-01: rate_changed(HIGH) -> 포함",
      any(c["slug"] == "weekly-holiday-allowance" for c in c01),
      f"후보={[c['slug'] for c in c01]}")

# B-02: wording_changed(LOW) -> severity 미달 제외
cfg = make_cfg("b02")
_, _, db = get_repos(cfg)
insert_calc(db, "c-wage-001", "weekly-holiday-allowance", "주휴수당 계산기")
insert_article(db, "art-wage-001", "c-wage-001", "wp-100", days_ago(200))
write_revision_state(cfg, {
    "min_wage_hourly": {"last_changed": "2026-08-01", "change_type": ["wording_changed"]}
})
c02 = _rms_candidates(cfg, {})
check("B-02: wording_changed(LOW) -> 제외", len(c02) == 0, f"후보 수={len(c02)}")

# B-03: 이미 processed -> SKIP
cfg = make_cfg("b03")
_, _, db = get_repos(cfg)
insert_calc(db, "c-wage-001", "weekly-holiday-allowance", "주휴수당 계산기")
insert_article(db, "art-wage-001", "c-wage-001", "wp-100", days_ago(200))
write_revision_state(cfg, {
    "min_wage_hourly": {"last_changed": "2026-08-01", "change_type": ["rate_changed"]}
})
already_done = {"min_wage_hourly__2026-08-01": {"result": "success", "article_id": "art-wage-001"}}
c03 = _rms_candidates(cfg, already_done)
check("B-03: 이미 processed -> SKIP",
      not any(c["slug"] == "weekly-holiday-allowance" for c in c03))

# B-04: IMPACT_MAP 없는 entity -> 제외
cfg = make_cfg("b04")
write_revision_state(cfg, {
    "unknown_entity_xyz": {"last_changed": "2026-08-01", "change_type": ["rate_changed"]}
})
c04 = _rms_candidates(cfg, {})
check("B-04: IMPACT_MAP 없는 entity -> 제외", not c04, f"후보={c04}")


# ── B-05~B-07: time-based 후보 시나리오 ─────────────────────────────────────

print("\n[time-based 시나리오]")

cfg = make_cfg("b0507")
_, _, db = get_repos(cfg)
insert_calc(db, "c-a-001", "four-insurances", "4대보험 계산기")
insert_calc(db, "c-b-001", "parental-leave", "육아휴직 계산기")
insert_calc(db, "c-c-001", "income-tax", "소득세 계산기")
insert_article(db, "art-a-001", "c-a-001", "wp-300", days_ago(400), history=[])
insert_article(db, "art-b-001", "c-b-001", "wp-400", days_ago(400),
               history=[rewrite_success_event(30)])
insert_article(db, "art-c-001", "c-c-001", "wp-500", days_ago(100), history=[])

from modules.rewrite_pipeline import _time_based_candidates
c0507 = _time_based_candidates(cfg)
ids = [c["article_id"] for c in c0507]
check("B-05: 400일, 쿨다운 없음 -> 포함", "art-a-001" in ids, f"IDs={ids}")
check("B-06: 400일, 30일 rewrite_success -> 쿨다운 제외", "art-b-001" not in ids, f"IDs={ids}")
check("B-07: 100일(stale 미달) -> 제외", "art-c-001" not in ids, f"IDs={ids}")


# ── B-08~B-13: collect_rewrite_candidates 통합 ──────────────────────────────

print("\n[collect_rewrite_candidates 통합]")

from modules.rewrite_pipeline import collect_rewrite_candidates

# B-08/10: 동일계산기 RMS+time-based 병합, 리라이트중 제외
cfg = make_cfg("b0810", limit=5)
_, _, db = get_repos(cfg)
insert_calc(db, "c-wage-002", "weekly-holiday-allowance", "주휴수당 계산기")
insert_calc(db, "c-ins-001", "four-insurances", "4대보험 계산기")
insert_calc(db, "c-run-001", "unemployment-benefit", "구직급여 계산기")
insert_article(db, "art-wage2-001", "c-wage-002", "wp-600", days_ago(400), history=[])
insert_article(db, "art-ins-001", "c-ins-001", "wp-700", days_ago(400), history=[])
insert_article(db, "art-run-001", "c-run-001", "wp-800", days_ago(200), status="리라이트중")
write_revision_state(cfg, {
    "min_wage_hourly": {"last_changed": "2026-08-01", "change_type": ["rate_changed"]}
})
c0810 = collect_rewrite_candidates(cfg)

wage_c = next((c for c in c0810 if c["calculator_id"] == "c-wage-002"), None)
run_c = next((c for c in c0810 if c["article_id"] == "art-run-001"), None)

check("B-08: 동일 계산기 RMS+time-based -> RMS reason 채택",
      wage_c is not None and wage_c["reason"]["type"] == "legal_change",
      f"reason={wage_c['reason']['type'] if wage_c else 'NOT_FOUND'}")
check("B-10: 리라이트중 article -> 제외", run_c is None)

# B-09: LIMIT=1
cfg_l1 = make_cfg("b09", limit=1)
_, _, db = get_repos(cfg_l1)
insert_calc(db, "c-wage-003", "weekly-holiday-allowance", "주휴수당 계산기")
insert_calc(db, "c-ins-002", "four-insurances", "4대보험 계산기")
insert_article(db, "art-wage3-001", "c-wage-003", "wp-601", days_ago(400), history=[])
insert_article(db, "art-ins-002", "c-ins-002", "wp-702", days_ago(400), history=[])
write_revision_state(cfg_l1, {
    "min_wage_hourly": {"last_changed": "2026-08-01", "change_type": ["rate_changed"]}
})
c09 = collect_rewrite_candidates(cfg_l1)
check("B-09: DAILY_REWRITE_LIMIT=1 -> 1건 이하", len(c09) <= 1, f"후보 수={len(c09)}")

# B-11: 필수 필드
REQUIRED_FIELDS = ["article_id", "calculator_id", "wp_post_id", "reason", "severity_rank"]
if wage_c:
    missing = [f for f in REQUIRED_FIELDS if f not in wage_c]
    check("B-11: 후보 필수 필드 누락 없음", not missing, f"누락={missing}")
else:
    check("B-11: 후보 필수 필드 누락 없음", False, "wage_c 없음")

# B-12: update_post 미사용 확인
import inspect
import modules.rewrite_pipeline as rp
src = inspect.getsource(rp.collect_rewrite_candidates)
check("B-12: collect_rewrite_candidates 에 update_post 미사용",
      "update_post" not in src)

# B-13: 빈 DB -> [] 반환
cfg_empty = make_cfg("b13_empty")
empty_result = collect_rewrite_candidates(cfg_empty)
check("B-13: 후보 0건 -> [] 반환, 오류 없음", empty_result == [], f"결과={empty_result}")


# ── B-14~B-15: reason 구조 상세 확인 ────────────────────────────────────────

print("\n[reason 구조 확인]")

cfg = make_cfg("b1415", limit=10)
_, _, db = get_repos(cfg)
insert_calc(db, "c-rms-001", "weekly-holiday-allowance", "주휴수당")
insert_calc(db, "c-time-001", "four-insurances", "4대보험")
insert_article(db, "art-rms-001", "c-rms-001", "wp-900", days_ago(100), history=[])
insert_article(db, "art-time-001", "c-time-001", "wp-910", days_ago(400), history=[])
write_revision_state(cfg, {
    "min_wage_hourly": {"last_changed": "2026-08-01", "change_type": ["rate_changed"]}
})
c1415 = collect_rewrite_candidates(cfg)
rms_c = next((c for c in c1415 if c.get("reason", {}).get("type") == "legal_change"), None)
time_c = next((c for c in c1415 if c.get("reason", {}).get("type") == "time_based"), None)

REASON_FIELDS = ["type", "source", "detected_at", "severity"]
if rms_c:
    missing_r = [f for f in REASON_FIELDS if not rms_c["reason"].get(f)]
    check("B-14: RMS reason 필수 필드 완전", not missing_r, f"누락={missing_r}")
    check("B-15: RMS rms_event_id 존재", bool(rms_c["reason"].get("rms_event_id")))
    check("B-15: RMS rms_event_id 형식 (entity__date)",
          "__" in str(rms_c["reason"].get("rms_event_id", "")))
    check("B-15: RMS article_id 존재", bool(rms_c.get("article_id")))
    check("B-15: RMS wp_post_id 존재", bool(rms_c.get("wp_post_id")))
    check("B-15: RMS calculator_id 존재", bool(rms_c.get("calculator_id")))
else:
    check("B-14/15: RMS 후보 존재", False, f"candidates={[c['reason']['type'] for c in c1415]}")

if time_c:
    missing_t = [f for f in REASON_FIELDS if not time_c["reason"].get(f)]
    check("B-14: time-based reason 필수 필드 완전", not missing_t, f"누락={missing_t}")
    check("B-14: time-based stale_days 존재", "stale_days" in time_c["reason"])
else:
    check("B-14: time-based 후보 존재", False, f"candidates={[c['reason']['type'] for c in c1415]}")


# ── 정리 ─────────────────────────────────────────────────────────────────────

gc.collect()  # SQLite 연결 해제 유도
try:
    shutil.rmtree(TMPDIR, ignore_errors=True)
except Exception:
    pass


# ── 결과 ─────────────────────────────────────────────────────────────────────

print()
if errors:
    print(f"PHASE B 실패 ({len(errors)}건)")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)
else:
    print("PHASE B PASS -- 모든 검증 항목 통과")
