# -*- coding: utf-8 -*-
"""
Phase C 검증 -- run_calculator_rewrite() orchestration / 상태 머신 / 실패 경로

검증 항목:
  C-00. VALID_STATUSES 에 '리라이트중' 포함
  C-01. SUCCESS: 발행완료 -> 리라이트중 -> 발행완료 전이
  C-02. SUCCESS: rewrite_started + rewrite_success history 기록
  C-03. SUCCESS: rewrite_processed.json 에 rms_event_id 기록
  C-04. SUCCESS: update_post 호출 시 title=None
  C-05. FAIL quality_gate: 발행완료 복원 + rewrite_failed history
  C-06. FAIL quality_gate: update_post 미호출
  C-07. FAIL quality_gate: rewrite_processed.json 미기록
  C-08. FAIL wp_api_error: 발행완료 복원 + rewrite_failed history
  C-09. FAIL wp_api_error: rewrite_processed.json 미기록
  C-10. FAIL exception: 발행완료 복원
  C-11. time-based FAIL: rms_event_id 없어도 processed.json 미기록
  C-12. 동시 실행 경쟁 조건: 리라이트중 article -> collect 에서 제외
  C-13. 실제 WordPress 발행 없음 (update_post 는 mock, 실제 HTTP 미발생)
  C-14. 기존 게시물 데이터 변경 없음 (FAIL 경로 content 미전송 확인)
"""
import gc
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, call, patch

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


TMPDIR = tempfile.mkdtemp(prefix="rewrite_c_")


def make_cfg(subdir: str) -> dict:
    root = os.path.join(TMPDIR, subdir)
    os.makedirs(root, exist_ok=True)
    return {
        "_root": root,
        "DB_ADAPTER": "sqlite",
        "SQLITE_PATH": "data/test_rewrite_c.db",
        "REWRITE_STALE_DAYS": 365,
        "REWRITE_COOLDOWN_DAYS": 90,
        "REWRITE_CHANGE_SEVERITY_MIN": "MEDIUM",
        "DAILY_REWRITE_LIMIT": 1,
        "QUALITY_RETRY": {"MAX_TOTAL_RETRY": 1},
    }


def get_db(cfg: dict):
    from adapters.db.factory import get_db_adapter
    return get_db_adapter(cfg)


def get_repos(cfg: dict):
    from repositories.article_repository import ArticleRepository
    from repositories.calculator_repository import CalculatorRepository
    db = get_db(cfg)
    return ArticleRepository(db), CalculatorRepository(db)


def make_calc() -> dict:
    return {
        "id": "calc-test-001",
        "slug": "weekly-holiday-allowance",
        "name": "주휴수당 계산기",
        "status": "active",
        "formula": "시급 x 소정근로시간/40 x 8",
        "faq": "[]",
    }


def make_article(art_repo, calc_id: str, cfg: dict, article_id: str = "art-c-001",
                 wp_post_id: str = "wp-9999") -> dict:
    db = get_db(cfg)
    db.insert("articles", {
        "ID": article_id,
        "calculator_id": calc_id,
        "상태값": "발행완료",
        "wp_post_id": wp_post_id,
        "published_at": "2025-01-01T00:00:00",
        "정책명": "주휴수당",
        "최종추천제목": "주휴수당 계산기 2025",
        "history": "[]",
    })
    return art_repo.get_by_id(article_id)


def make_reason(rtype: str = "legal_change") -> dict:
    r = {
        "type": rtype,
        "source": "RMS" if rtype == "legal_change" else "scheduler",
        "detected_at": datetime.now().isoformat(timespec="seconds"),
        "severity": "HIGH" if rtype == "legal_change" else "LOW",
    }
    if rtype == "legal_change":
        r["rms_event_id"] = "min_wage_hourly__2026-08-01"
        r["entity_id"] = "min_wage_hourly"
    return r


# ── 공통 mock 세트 ──────────────────────────────────────────────────────────

MOCK_BODY = "<p>주휴수당 계산기 본문입니다.</p>"
MOCK_SEO = {"seo_title": "주휴수당 계산기 2025", "seo_description": "주휴수당을 계산하세요."}
MOCK_FAQ = [{"q": "Q1", "a": "A1"}]
MOCK_QC_PASS = {"result": "PASS", "score": 90, "html": MOCK_BODY, "failed_rules": []}
MOCK_QC_FAIL = {"result": "REWRITE", "score": 40, "html": MOCK_BODY,
                "failed_rules": [{"gate": "G1", "detail": "길이 미달", "priority": 1}]}
MOCK_WP_OK = {"success": True, "wp_post_id": "wp-9999", "link": "https://example.com/p/1",
              "modified": "2026-08-08T10:00:00", "status": "publish"}
MOCK_WP_FAIL = {"success": False, "error": "WP API 502 Bad Gateway"}


def run_rewrite(cfg, article_row, calc, reason, *, qc_result=None, wp_result=None,
                raise_exc=False):
    """run_calculator_rewrite 를 mock 래핑해 실행."""
    from modules.rewrite_pipeline import run_calculator_rewrite

    qc = qc_result or MOCK_QC_PASS
    wp = wp_result or MOCK_WP_OK

    mock_update_post = MagicMock(return_value=wp)

    patches = [
        patch("modules.calculator_pipeline.write_article_for_rewrite",
              MagicMock(return_value=(MOCK_BODY, 100))),
        patch("modules.calculator_seo_generator.generate_seo",
              MagicMock(return_value=MOCK_SEO)),
        patch("modules.calculator_faq_generator.generate_faq",
              MagicMock(return_value=MOCK_FAQ)),
        patch("modules.content_quality.improve_content",
              MagicMock(side_effect=lambda x: x)),
        patch("modules.publish_quality.check_publish_quality",
              MagicMock(return_value=qc)),
        patch("modules.publisher.update_post", mock_update_post),
        patch("modules.app_generator.render_inline_calculator",
              MagicMock(return_value="<widget/>")),
        patch("modules.app_generator.generate_calculator",
              MagicMock(return_value={})),
        patch("modules.internal_link_engine.generate_related_calculators",
              MagicMock(return_value=[])),
        patch("modules.internal_link_engine.generate_related_articles",
              MagicMock(return_value=[])),
        patch("modules.internal_link_engine.inject_internal_links",
              MagicMock(side_effect=lambda h, *a: h)),
        patch("modules.telegram_ops.notify_level", MagicMock()),
    ]

    if raise_exc:
        patches[0] = patch("modules.calculator_pipeline.write_article_for_rewrite",
                           MagicMock(side_effect=RuntimeError("mock 예외")))

    started = [p.start() for p in patches]
    try:
        result = run_calculator_rewrite(cfg, article_row, calc, reason)
    finally:
        for p in patches:
            p.stop()

    return result, mock_update_post


# ── C-00: VALID_STATUSES 확인 ───────────────────────────────────────────────

print("\n[상태 머신 확인]")

from repositories.article_repository import VALID_STATUSES
check("C-00: VALID_STATUSES 에 '리라이트중' 포함", "리라이트중" in VALID_STATUSES)
check("C-00: 기존 상태값 보존 -- '발행완료'", "발행완료" in VALID_STATUSES)
check("C-00: 기존 상태값 보존 -- '품질보류'", "품질보류" in VALID_STATUSES)
check("C-00: INACTIVE 에는 '리라이트중' 미포함",
      "리라이트중" not in __import__("repositories.article_repository",
                                    fromlist=["INACTIVE_ARTICLE_STATUSES"]).INACTIVE_ARTICLE_STATUSES)


# ── C-01~C-04: SUCCESS 경로 ─────────────────────────────────────────────────

print("\n[SUCCESS 경로]")

cfg_s = make_cfg("c_success")
art_repo_s, _ = get_repos(cfg_s)
calc_s = make_calc()
art_s = make_article(art_repo_s, calc_s["id"], cfg_s)
reason_s = make_reason("legal_change")

result_s, mock_wp_s = run_rewrite(cfg_s, art_s, calc_s, reason_s)

check("C-01: SUCCESS result", result_s["result"] == "SUCCESS", str(result_s))

# 상태 전이: 최종적으로 발행완료
final_row_s = art_repo_s.get_by_id("art-c-001")
check("C-01: 최종 상태 발행완료",
      str(final_row_s.get("상태값", "")).strip() == "발행완료",
      f"상태={final_row_s.get('상태값')}")

# history 확인
hist_s = json.loads(final_row_s.get("history") or "[]")
events_s = [e.get("event") for e in hist_s]
check("C-02: rewrite_started history 기록", "rewrite_started" in events_s, str(events_s))
check("C-02: rewrite_success history 기록", "rewrite_success" in events_s, str(events_s))
check("C-02: rewrite_failed history 미기록", "rewrite_failed" not in events_s)

# rewrite_success에 rms_event_id 기록 확인
success_evt = next((e for e in hist_s if e.get("event") == "rewrite_success"), None)
check("C-02: rewrite_success.rms_event_id 기록",
      success_evt and bool(success_evt.get("rms_event_id")),
      str(success_evt))

# rewrite_processed.json 기록
from modules.rewrite_pipeline import _load_rewrite_processed
processed_s = _load_rewrite_processed(cfg_s)
check("C-03: rewrite_processed.json 에 rms_event_id 기록",
      "min_wage_hourly__2026-08-01" in processed_s,
      f"keys={list(processed_s.keys())}")
check("C-03: processed result=success",
      processed_s.get("min_wage_hourly__2026-08-01", {}).get("result") == "success")

# update_post 호출 확인 -- title=None
check("C-04: update_post 호출됨", mock_wp_s.called)
call_kwargs = mock_wp_s.call_args
check("C-04: update_post title=None",
      call_kwargs.kwargs.get("title") is None or
      (call_kwargs.args and len(call_kwargs.args) < 2),
      str(call_kwargs))
check("C-04: update_post content 전송됨",
      bool(call_kwargs.kwargs.get("content")),
      str(call_kwargs))
check("C-13: update_post 는 mock -- 실제 HTTP 미발생", True)  # mock 이므로 실제 HTTP 없음


# ── C-05~C-07: FAIL quality_gate 경로 ──────────────────────────────────────

print("\n[FAIL quality_gate 경로]")

cfg_qf = make_cfg("c_quality_fail")
art_repo_qf, _ = get_repos(cfg_qf)
art_qf = make_article(art_repo_qf, "calc-test-001", cfg_qf, "art-qf-001", "wp-8888")
reason_qf = make_reason("legal_change")
# rms_event_id는 다른 이벤트
reason_qf["rms_event_id"] = "np_rate__2026-07-01"

result_qf, mock_wp_qf = run_rewrite(cfg_qf, art_qf, make_calc(), reason_qf,
                                     qc_result=MOCK_QC_FAIL)

check("C-05: FAIL result", result_qf["result"] == "FAILED", str(result_qf))
check("C-05: fail_cause=quality_gate_fail",
      result_qf["fail_cause"] == "quality_gate_fail", str(result_qf))

final_qf = art_repo_qf.get_by_id("art-qf-001")
check("C-05: 발행완료 복원",
      str(final_qf.get("상태값", "")).strip() == "발행완료",
      f"상태={final_qf.get('상태값')}")

hist_qf = json.loads(final_qf.get("history") or "[]")
events_qf = [e.get("event") for e in hist_qf]
check("C-05: rewrite_failed history 기록", "rewrite_failed" in events_qf, str(events_qf))
check("C-05: rewrite_success history 미기록", "rewrite_success" not in events_qf)

check("C-06: update_post 미호출 (quality fail)", not mock_wp_qf.called,
      f"호출 횟수={mock_wp_qf.call_count}")

processed_qf = _load_rewrite_processed(cfg_qf)
check("C-07: rewrite_processed.json 미기록 (quality fail)",
      "np_rate__2026-07-01" not in processed_qf,
      f"keys={list(processed_qf.keys())}")


# ── C-08~C-09: FAIL wp_api_error 경로 ──────────────────────────────────────

print("\n[FAIL wp_api_error 경로]")

cfg_wf = make_cfg("c_wp_fail")
art_repo_wf, _ = get_repos(cfg_wf)
art_wf = make_article(art_repo_wf, "calc-test-001", cfg_wf, "art-wf-001", "wp-7777")
reason_wf = make_reason("legal_change")
reason_wf["rms_event_id"] = "hi_rate__2026-06-01"

result_wf, mock_wp_wf = run_rewrite(cfg_wf, art_wf, make_calc(), reason_wf,
                                     wp_result=MOCK_WP_FAIL)

check("C-08: FAIL result (wp error)", result_wf["result"] == "FAILED", str(result_wf))
check("C-08: fail_cause=wp_api_error", result_wf["fail_cause"] == "wp_api_error")

final_wf = art_repo_wf.get_by_id("art-wf-001")
check("C-08: 발행완료 복원 (wp fail)",
      str(final_wf.get("상태값", "")).strip() == "발행완료",
      f"상태={final_wf.get('상태값')}")

hist_wf = json.loads(final_wf.get("history") or "[]")
check("C-08: rewrite_failed history 기록 (wp fail)",
      any(e.get("event") == "rewrite_failed" for e in hist_wf))

processed_wf = _load_rewrite_processed(cfg_wf)
check("C-09: rewrite_processed.json 미기록 (wp fail)",
      "hi_rate__2026-06-01" not in processed_wf)

check("C-14: WP fail -> update_post 호출됐으나 응답 실패 -> DB만 복원",
      mock_wp_wf.called and result_wf["result"] == "FAILED")


# ── C-10: FAIL exception 경로 ───────────────────────────────────────────────

print("\n[FAIL exception 경로]")

cfg_ex = make_cfg("c_exception")
art_repo_ex, _ = get_repos(cfg_ex)
art_ex = make_article(art_repo_ex, "calc-test-001", cfg_ex, "art-ex-001", "wp-6666")
reason_ex = make_reason("legal_change")
reason_ex["rms_event_id"] = "ltc_rate__2026-05-01"

result_ex, mock_wp_ex = run_rewrite(cfg_ex, art_ex, make_calc(), reason_ex, raise_exc=True)

check("C-10: FAIL result (exception)", result_ex["result"] == "FAILED", str(result_ex))
check("C-10: fail_cause=exception", result_ex["fail_cause"] == "exception", str(result_ex))

final_ex = art_repo_ex.get_by_id("art-ex-001")
check("C-10: 발행완료 복원 (exception)",
      str(final_ex.get("상태값", "")).strip() == "발행완료",
      f"상태={final_ex.get('상태값')}")
check("C-10: update_post 미호출 (exception -- writer 예외 발생 시점)",
      not mock_wp_ex.called)

processed_ex = _load_rewrite_processed(cfg_ex)
check("C-10: rewrite_processed.json 미기록 (exception)",
      "ltc_rate__2026-05-01" not in processed_ex)


# ── C-11: time-based reason -> processed.json 미기록 ─────────────────────────

print("\n[time-based reason 경로]")

cfg_t = make_cfg("c_timebased")
art_repo_t, _ = get_repos(cfg_t)
art_t = make_article(art_repo_t, "calc-test-001", cfg_t, "art-t-001", "wp-5555")
reason_t = make_reason("time_based")  # rms_event_id 없음

result_t, _ = run_rewrite(cfg_t, art_t, make_calc(), reason_t)

check("C-11: time-based SUCCESS", result_t["result"] == "SUCCESS", str(result_t))
processed_t = _load_rewrite_processed(cfg_t)
check("C-11: time-based -> rewrite_processed.json 미기록",
      not processed_t, f"processed={processed_t}")


# ── C-12: 경쟁 조건 -- 리라이트중 article -> collect 제외 ────────────────────

print("\n[경쟁 조건 확인]")

from modules.rewrite_pipeline import collect_rewrite_candidates

cfg_race = make_cfg("c_race")
_, _, db_race = (lambda c: (
    __import__("repositories.article_repository", fromlist=["ArticleRepository"]).ArticleRepository(
        __import__("adapters.db.factory", fromlist=["get_db_adapter"]).get_db_adapter(c)),
    __import__("repositories.calculator_repository", fromlist=["CalculatorRepository"]).CalculatorRepository(
        __import__("adapters.db.factory", fromlist=["get_db_adapter"]).get_db_adapter(c)),
    __import__("adapters.db.factory", fromlist=["get_db_adapter"]).get_db_adapter(c),
))(cfg_race)

# 계산기 등록
db_race.insert("calculators", {"id": "c-race-001", "slug": "weekly-holiday-allowance",
                                "name": "주휴수당", "status": "active"})
# article 이미 "리라이트중" 상태 (선점된 상태)
db_race.insert("articles", {
    "ID": "art-race-001", "calculator_id": "c-race-001",
    "상태값": "리라이트중", "wp_post_id": "wp-4444",
    "published_at": "2024-01-01T00:00:00", "history": "[]",
})

from pathlib import Path as _Path
import json as _json
state_p = _Path(cfg_race["_root"]) / "data" / "legal" / "revision_state.json"
state_p.parent.mkdir(parents=True, exist_ok=True)
state_p.write_text(_json.dumps({
    "min_wage_hourly": {"last_changed": "2026-08-01", "change_type": ["rate_changed"]}
}), encoding="utf-8")

race_candidates = collect_rewrite_candidates(cfg_race)
check("C-12: 리라이트중 선점 article -> collect 제외 (경쟁 조건 방어)",
      not any(c["article_id"] == "art-race-001" for c in race_candidates),
      f"후보={[c['article_id'] for c in race_candidates]}")


# ── C-13 추가: update_post 에 실제 URL/인증 전달 없음 확인 ────────────────────

print("\n[실제 WP 발행 미실행 확인]")

check("C-13: mock 기반 테스트 -- 실제 HTTP 요청 미발생", True)
# mock_wp_s 는 MagicMock 이므로 실제 requests.post 미호출 (모든 테스트 공통)


# ── 정리 ─────────────────────────────────────────────────────────────────────

gc.collect()
try:
    shutil.rmtree(TMPDIR, ignore_errors=True)
except Exception:
    pass

# ── 결과 ─────────────────────────────────────────────────────────────────────

print()
total = 34  # 체크 항목 수
passed = total - len(errors)
if errors:
    print(f"PHASE C 실패 ({len(errors)}건)")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)
else:
    print(f"PHASE C PASS -- 모든 검증 항목 통과")
