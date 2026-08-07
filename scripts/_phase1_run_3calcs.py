# -*- coding: utf-8 -*-
"""
Phase 1: 3개 계산기 운영 데이터 생성 + 검증
Phase 2: 안정화 확인 (SQLite 누적 / Sheets-SQLite row count 일치 / pending_sync=0)

대상: 주휴수당(weekly-holiday-allowance), 실업급여(unemployment-benefit), 퇴직금(severance-pay)
"""
import sys, io, re, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"C:\Users\연수\Desktop\블로그자동_v12")

from datetime import datetime
from pathlib import Path

from modules.config_loader import load_config
from adapters.db.factory import get_db_adapter
from adapters.db.dual_adapter import list_pending_sync
from repositories.calculator_repository import CalculatorRepository
from repositories.article_repository import ArticleRepository

cfg = load_config()
assert cfg.get("DB_ADAPTER","").lower() == "dual", "DB_ADAPTER must be dual"

PASS = "PASS ✅"
FAIL = "FAIL ❌"
WARN = "WARN ⚠️"
results = {}

def check(name, condition, evidence="", warn=False):
    if condition is True:
        status = PASS
    elif warn and condition == "warn":
        status = WARN
    else:
        status = FAIL
    results[name] = status
    print(f"  [{status}] {name}")
    if evidence:
        print(f"         증거: {evidence}")
    return condition is True

TARGET_SLUGS = [
    "weekly-holiday-allowance",
    "unemployment-benefit",
    "severance-pay",
]
SLUG_NAMES = {
    "weekly-holiday-allowance": "주휴수당",
    "unemployment-benefit":     "실업급여",
    "severance-pay":            "퇴직금",
}

# ══════════════════════════════════════════════════════════════
# STEP 0: 계산기 시드 (idempotent)
# ══════════════════════════════════════════════════════════════
print("=" * 60)
print("STEP 0: 계산기 시드 등록")
print("=" * 60)
from modules.calculator_seed import seed_all
seed_result = seed_all(cfg)
print(f"  시드 결과: calcs_added={seed_result.get('calculators_added',0)}  templates_added={seed_result.get('templates_added',0)}")

db = get_db_adapter(cfg)
calc_repo = CalculatorRepository(db)
art_repo  = ArticleRepository(db)

all_calcs = calc_repo.get_all()
CALC_IDS = {}
for slug in TARGET_SLUGS:
    hit = [c for c in all_calcs if c.get("slug") == slug]
    if hit:
        CALC_IDS[slug] = hit[0].get("id","")
        print(f"  {SLUG_NAMES[slug]}: id={CALC_IDS[slug]}, status={hit[0].get('status','')}")
    else:
        print(f"  {SLUG_NAMES[slug]}: ⚠ 시드 후에도 미발견!")

print()
check("3개 계산기 모두 DB에 등록됨",
      len([s for s in TARGET_SLUGS if s in CALC_IDS]) == 3,
      f"발견={list(CALC_IDS.keys())}")

# ══════════════════════════════════════════════════════════════
# STEP 1: 3개 파이프라인 순차 실행
# ══════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("STEP 1: 파이프라인 실행 (3개 계산기)")
print("=" * 60)

from modules.calculator_pipeline import run_calculator_once

pipe_results = {}
for slug in TARGET_SLUGS:
    cid = CALC_IDS.get(slug)
    name = SLUG_NAMES[slug]
    if not cid:
        pipe_results[slug] = {"error": "calc_id 없음"}
        continue

    print()
    print(f"--- [{name}] cid={cid} ---")
    t_start = datetime.now()
    try:
        result = run_calculator_once(cfg, max_count=1, only_cid=cid, allow_duplicate=False)
        elapsed = (datetime.now() - t_start).total_seconds()
        result["elapsed"] = elapsed
        pipe_results[slug] = result
        produced = result.get("produced", 0)
        reason   = result.get("reason", "")
        pub_info = result.get("published")
        status_line = (f"produced={produced}, reason={reason}, time={elapsed:.0f}s")
        if pub_info:
            status_line += f", title={pub_info.get('title','')[:40]}"
        print(f"  완료: {status_line}")
    except Exception as e:
        elapsed = (datetime.now() - t_start).total_seconds()
        pipe_results[slug] = {"error": str(e), "elapsed": elapsed}
        print(f"  오류: {e}")

# ══════════════════════════════════════════════════════════════
# STEP 2: Phase 1 검증
# ══════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("STEP 2: Phase 1 검증")
print("=" * 60)

# 2-A. 파이프라인 실행 결과
print()
print("[2-A] 파이프라인 실행 결과")
for slug in TARGET_SLUGS:
    name = SLUG_NAMES[slug]
    r = pipe_results.get(slug, {})
    if "error" in r:
        check(f"{name} 파이프라인 실행 완료", False, f"오류: {r['error']}")
        continue
    produced = r.get("produced", 0)
    reason   = r.get("reason", "")
    # produced=1이면 정상, 0이면 품질보류/스킵도 가능하므로 reason 확인
    ok = produced >= 1 or reason in ("ok",)
    check(f"{name} 파이프라인 실행 완료 (produced={produced})",
          produced >= 1,
          f"reason={reason}, elapsed={r.get('elapsed',0):.0f}s")

# 2-B. 마스터_DB (Sheets + SQLite) 기록 확인
print()
print("[2-B] 마스터_DB 양쪽 기록 확인")
db2 = get_db_adapter(cfg)
sh_arts = db2._primary.get_all("articles", force_refresh=True)
sq_arts = db2._secondary.get_all("articles")

for slug in TARGET_SLUGS:
    name = SLUG_NAMES[slug]
    cid  = CALC_IDS.get(slug, "")
    sh_rel = [a for a in sh_arts if str(a.get("calculator_id","")) == cid]
    sq_rel = [a for a in sq_arts if str(a.get("calculator_id","")) == cid]
    check(f"{name} 마스터_DB → Sheets 기록", len(sh_rel) >= 1, f"{len(sh_rel)}건")
    check(f"{name} 마스터_DB → SQLite 기록", len(sq_rel) >= 1, f"{len(sq_rel)}건")
    if sh_rel and sq_rel:
        sh_ids = {a.get("ID","") for a in sh_rel}
        sq_ids = {a.get("ID","") for a in sq_rel}
        check(f"{name} 마스터_DB Sheets==SQLite (ID 교집합)",
              len(sh_ids & sq_ids) > 0,
              f"Sheets={list(sh_ids)[:2]}, SQLite={list(sq_ids)[:2]}")
        # 상태값 확인
        sh_statuses = [a.get("상태값","") for a in sh_rel]
        check(f"{name} 마스터_DB 상태값 정상",
              any(s in ("발행완료","검수대기","품질보류") for s in sh_statuses),
              f"상태값={sh_statuses}")

# 2-C. 운영로그 양쪽 기록 확인
print()
print("[2-C] 운영로그 양쪽 기록 확인")
# 파이프라인이 완료된 경우 운영로그는 sheet_sync.append_log로 기록됨
# log에서 파이프라인 실행 관련 로그를 확인 (실행일시 기준 오늘)
sh_logs = db2._primary.get_all("logs", force_refresh=True)
sq_logs = db2._secondary.get_all("logs")
today = datetime.now().strftime("%Y-%m-%d")
sh_today = [l for l in sh_logs if str(l.get("실행일시","")).startswith(today)]
sq_today = [l for l in sq_logs if str(l.get("실행일시","")).startswith(today)]
check("운영로그 → Sheets 오늘 기록 존재", len(sh_today) >= 1,
      f"오늘 로그 {len(sh_today)}건")
check("운영로그 → SQLite 오늘 기록 존재", len(sq_today) >= 1,
      f"오늘 로그 {len(sq_today)}건")
check("운영로그 Sheets-SQLite 건수 일치", len(sh_today) == len(sq_today),
      f"Sheets={len(sh_today)}, SQLite={len(sq_today)}")

# 2-D. HTML 구조 검증 (WP에서 직접 fetch)
print()
print("[2-D] HTML 구조 검증 (7-H2 / H1 / ALT / 이미지위치)")
import requests as _req

def _wp_auth(c):
    u = c.get("WORDPRESS_USERNAME", "")
    p = c.get("WORDPRESS_APP_PASSWORD") or c.get("WORDPRESS_PASSWORD", "")
    return (u, p) if u and p else None

WP_URL = cfg.get("WORDPRESS_URL", "").rstrip("/")
auth = _wp_auth(cfg)

EXPECTED_H2 = ["계산기소개","입력방법","결과확인","계산원리","주의사항","FAQ","계산기 사용하기"]

for slug in TARGET_SLUGS:
    name = SLUG_NAMES[slug]
    cid  = CALC_IDS.get(slug, "")
    sh_rel = [a for a in sh_arts if str(a.get("calculator_id","")) == cid]

    if not sh_rel:
        print(f"  [{name}] 마스터_DB 기록 없음 → HTML 검증 스킵")
        continue

    # 발행완료 or 검수대기 항목 우선
    target_art = next(
        (a for a in sh_rel if a.get("상태값") in ("발행완료","검수대기")),
        sh_rel[-1]
    )

    wp_post_id = str(target_art.get("wp_post_id",""))
    status_val = target_art.get("상태값","")
    title_val  = target_art.get("최종추천제목","")[:40]

    print(f"  [{name}] 상태={status_val} wp_post_id={wp_post_id} 제목={title_val}")

    if status_val == "품질보류":
        q_status = target_art.get("quality_status","")
        check(f"{name} HTML 구조 (품질보류 — 발행 없음, 게이트 결과 확인)",
              q_status in ("REWRITE","LEGAL_UNVERIFIED"),
              f"quality_status={q_status} — 발행 안 됨")
        continue

    if not wp_post_id or not auth or not WP_URL:
        check(f"{name} HTML 구조 — WP fetch 불가", False,
              f"wp_post_id={wp_post_id}, auth={bool(auth)}, url={WP_URL}")
        continue

    try:
        resp = _req.get(
            f"{WP_URL}/wp-json/wp/v2/posts/{wp_post_id}",
            params={"context": "edit"},
            auth=auth, timeout=15
        )
        if resp.status_code != 200:
            check(f"{name} WP 포스트 fetch 성공", False,
                  f"HTTP {resp.status_code}")
            continue

        post_data = resp.json()
        html = post_data.get("content", {}).get("rendered", "") or post_data.get("content", "")

        # H2 수집
        h2s = re.findall(r'<h2[^>]*>\s*(.*?)\s*</h2>', html, re.I | re.S)
        h2_clean = [re.sub(r'<[^>]+>','',h).strip() for h in h2s]

        check(f"{name} H2 개수=7", len(h2s) == 7, f"H2={h2_clean}")

        for exp_h2 in EXPECTED_H2:
            found = any(exp_h2 in h for h in h2_clean)
            check(f"{name} H2[{exp_h2}] 존재", found,
                  f"H2목록={h2_clean}")

        # H1 중복 없음
        h1s = re.findall(r'<h1[^>]*>', html, re.I)
        check(f"{name} H1 중복 없음 (body에 H1=0)", len(h1s) == 0,
              f"body H1 수={len(h1s)}")

        # ALT 속성 (빈 alt 없음)
        imgs = re.findall(r'<img[^>]+>', html, re.I)
        missing_alt = [img for img in imgs
                       if 'alt=""' in img.lower() or 'alt' not in img.lower()]
        check(f"{name} 이미지 ALT 누락 없음", len(missing_alt) == 0,
              f"ALT 누락={len(missing_alt)}/{len(imgs)} 이미지")

        # 이미지 위치 (계산원리 섹션 직후)
        if imgs:
            # 본문이미지는 <계산원리> H2 이후, 다음 H2 이전에 위치해야 함
            m = re.search(r'<h2[^>]*>계산\s*원리</h2>(.*?)(?=<h2)', html, re.I | re.S)
            body_img_after_calc = bool(m and re.search(r'<img', m.group(1), re.I))
            check(f"{name} 본문이미지 위치 (계산원리 직후)", body_img_after_calc,
                  f"계산원리 직후 이미지={'있음' if body_img_after_calc else '없음'}")

    except Exception as e:
        check(f"{name} WP HTML 검증", False, f"오류: {e}")

# ══════════════════════════════════════════════════════════════
# STEP 3: Phase 2 — 안정화 확인
# ══════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("STEP 3: Phase 2 — 안정화 확인")
print("=" * 60)

# 3-A. SQLite 데이터 누적 확인
print()
print("[3-A] SQLite 데이터 누적 확인")
db3 = get_db_adapter(cfg)
sq_all_arts  = db3._secondary.get_all("articles")
sq_all_calcs = db3._secondary.get_all("calculators")
sq_all_logs  = db3._secondary.get_all("logs")

check("SQLite articles 테이블 데이터 누적", len(sq_all_arts) >= 1,
      f"{len(sq_all_arts)}행")
check("SQLite calculators 테이블 데이터 누적", len(sq_all_calcs) >= 3,
      f"{len(sq_all_calcs)}행")
check("SQLite logs 테이블 데이터 누적", len(sq_all_logs) >= 1,
      f"{len(sq_all_logs)}행")

# 3-B. Sheets vs SQLite row count 일치
print()
print("[3-B] Sheets vs SQLite row count 일치 확인")
db3_primary = get_db_adapter(cfg)
sh_all_arts  = db3_primary._primary.get_all("articles",    force_refresh=True)
sh_all_calcs = db3_primary._primary.get_all("calculators", force_refresh=True)
sh_all_logs  = db3_primary._primary.get_all("logs",        force_refresh=True)

for table, sh_rows, sq_rows in [
    ("articles(마스터_DB)", sh_all_arts, sq_all_arts),
    ("calculators",         sh_all_calcs, sq_all_calcs),
    ("logs(운영로그)",      sh_all_logs,  sq_all_logs),
]:
    match = len(sh_rows) == len(sq_rows)
    check(f"{table}: Sheets({len(sh_rows)}) == SQLite({len(sq_rows)})", match,
          f"차이={abs(len(sh_rows)-len(sq_rows))}행")

# 3-C. pending_sync 계속 0 유지
print()
print("[3-C] pending_sync 0 유지 확인")
pending = list_pending_sync()
check("pending_sync.json 대기 항목 0건", len(pending) == 0,
      f"대기={len(pending)}건")
if pending:
    for p in pending:
        print(f"    ⚠ 미처리: op={p.get('op')} table={p.get('table')} err={p.get('error','')[:60]}")

# ══════════════════════════════════════════════════════════════
# 최종 보고
# ══════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("최종 보고")
print("=" * 60)
all_pass  = all(v == PASS for v in results.values())
warn_only = all(v in (PASS, WARN) for v in results.values())
fail_items = [k for k, v in results.items() if v == FAIL]
warn_items = [k for k, v in results.items() if v == WARN]

for name, status in results.items():
    print(f"  {status}  {name}")

print()
# 파이프라인별 최종 상태
print("파이프라인 요약:")
for slug in TARGET_SLUGS:
    name = SLUG_NAMES[slug]
    r    = pipe_results.get(slug, {})
    cid  = CALC_IDS.get(slug,"")
    sh_r = [a for a in sh_arts if str(a.get("calculator_id","")) == cid]
    statuses = [a.get("상태값","") for a in sh_r]
    titles   = [a.get("최종추천제목","")[:35] for a in sh_r]
    print(f"  {name}: produced={r.get('produced','-')} 상태={statuses} 제목={titles}")

print()
if all_pass:
    print("결론: 전체 PASS ✅")
    print("→ 운영 기준 데이터 확보 완료 — Feature Freeze 준비완료")
elif warn_only:
    print(f"결론: PASS (경고 {len(warn_items)}건) ⚠️")
    print(f"→ 경고 항목: {warn_items}")
    print("→ 운영 기준 데이터 확보 완료 — Feature Freeze 준비완료 (경고 확인 필요)")
else:
    print(f"결론: FAIL ❌ ({len(fail_items)}건 실패)")
    for f in fail_items:
        print(f"  ✗ {f}")

import sys
sys.exit(0 if (all_pass or warn_only) else 1)
