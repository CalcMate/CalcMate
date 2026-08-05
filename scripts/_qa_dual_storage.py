# -*- coding: utf-8 -*-
"""
QA-0: 동시저장 검증 (Dual Storage Verification)

1단계: 기본 동기화 — qa_sync_test_001 → Sheets + SQLite 동시 기록 확인
2단계 A: Sheets OK + Local 실패 → 재시도 큐 생성 확인
2단계 B: Sheets 실패 + Local OK → sync_pending 마킹 확인 (데이터 유실 없음)
3단계: 테스트 데이터 정리

결론 조건: 모든 단계 PASS 시에만 PASS 선언
"""
import sys, io, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"C:\Users\연수\Desktop\블로그자동_v12")

from unittest.mock import patch, MagicMock
from datetime import datetime
from pathlib import Path

from modules.config_loader import load_config
from adapters.db.dual_adapter import DualAdapter, list_pending_sync, _SYNC_QUEUE_PATH

cfg = load_config()

# ── 테스트 픽스처 ──────────────────────────────────────────────
TEST_ID = "qa_sync_test_001"
TEST_CALC = {
    "id":        TEST_ID,
    "name":      "[QA] 동시저장 검증 테스트",
    "slug":      "qa-sync-test-001",
    "category":  "qa",
    "status":    "draft",
    "site_id":   "qa_site",
    "created_at": datetime.now().isoformat(),
}

PASS = "PASS ✅"
FAIL = "FAIL ❌"
results = {}

def check(name, condition, evidence=""):
    status = PASS if condition else FAIL
    results[name] = status
    print(f"  [{status}] {name}")
    if evidence:
        print(f"         증거: {evidence}")
    return condition


# ══════════════════════════════════════════════════════════════
# 1단계: 기본 동기화 확인
# ══════════════════════════════════════════════════════════════
print("=" * 60)
print("1단계 — 기본 동기화 확인")
print("=" * 60)

adapter = DualAdapter(cfg)

# 사전 정리: 혹시 잔여 테스트 데이터가 있으면 제거
try:
    existing = adapter.get_where("calculators", {"id": TEST_ID})
    if existing:
        adapter.delete("calculators", TEST_ID)
        print(f"  사전 정리: 잔여 {TEST_ID} 제거됨")
except Exception:
    pass

# 1-1. Insert
print()
print("[1-1] 테스트 계산기 삽입")
try:
    result_id = adapter.insert("calculators", dict(TEST_CALC))
    check("insert 반환 ID == TEST_ID", result_id == TEST_ID,
          f"반환값={result_id}")
except Exception as e:
    check("insert 반환 ID == TEST_ID", False, f"예외: {e}")
    print("  → insert 실패, 이후 검증 불가")
    sys.exit(1)

# 1-2. Sheets 확인 (force_refresh=True로 TTL 캐시 무시)
print()
print("[1-2] Google Sheets 기록 확인")
sheets_rows = adapter._primary.get_all("calculators", force_refresh=True)
sheets_hit = [r for r in sheets_rows if str(r.get("id", "")) == TEST_ID]
check("Sheets calculators 탭에 기록됨",
      bool(sheets_hit),
      f"Sheets 조회 {len(sheets_hit)}건")
if sheets_hit:
    r = sheets_hit[0]
    check("ID 동일", r.get("id") == TEST_ID, f"id={r.get('id')}")
    check("status=draft", r.get("status") == "draft", f"status={r.get('status')}")
    check("slug 일치", r.get("slug") == TEST_CALC["slug"], f"slug={r.get('slug')}")

# 1-3. SQLite 확인
print()
print("[1-3] SQLite 기록 확인")
sqlite_rows = adapter._secondary.get_all("calculators")
sqlite_hit = [r for r in sqlite_rows if str(r.get("id", "")) == TEST_ID]
check("SQLite calculators 테이블에 기록됨",
      bool(sqlite_hit),
      f"SQLite 조회 {len(sqlite_hit)}건")
if sqlite_hit:
    r = sqlite_hit[0]
    check("SQLite ID 동일", r.get("id") == TEST_ID, f"id={r.get('id')}")
    check("SQLite sync_status=synced", r.get("sync_status") == "synced",
          f"sync_status={r.get('sync_status')}")

# 1-4. ID 동일성 (Sheets vs SQLite)
if sheets_hit and sqlite_hit:
    print()
    print("[1-4] 양쪽 ID 일치 대조")
    check("Sheets.id == SQLite.id",
          sheets_hit[0].get("id") == sqlite_hit[0].get("id"),
          f"Sheets={sheets_hit[0].get('id')}, SQLite={sqlite_hit[0].get('id')}")

# 1단계 집계
step1_ok = all(v == PASS for k, v in results.items())
print()
print(f"1단계 결과: {'PASS ✅' if step1_ok else 'FAIL ❌ — 일부 항목 실패'}")


# ══════════════════════════════════════════════════════════════
# 2단계 A: Sheets OK + Local DB 실패 → 재시도 큐 생성
# ══════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("2단계 A — Sheets OK + Local DB 실패 → 재시도 큐")
print("=" * 60)

# 사전: 현재 큐 상태 기록
queue_before = list_pending_sync()
queue_count_before = len(queue_before)
print(f"  사전 큐 대기 수: {queue_count_before}")

TEST_ID_A = "qa_sync_test_001_A"
TEST_CALC_A = {**TEST_CALC, "id": TEST_ID_A, "slug": "qa-sync-test-001-a"}

# SQLiteAdapter.insert 를 강제로 실패시킴
adapter_a = DualAdapter(cfg)
# 원본 SQLite insert 백업 후 패치
orig_sqlite_insert = adapter_a._secondary.insert

def _fail_sqlite_insert(table, row):
    raise RuntimeError("QA MOCK: SQLite 강제 실패")

adapter_a._secondary.insert = _fail_sqlite_insert

print()
print("[2A-1] Sheets OK + SQLite 강제 실패로 insert 시도")
try:
    rid = adapter_a.insert("calculators", dict(TEST_CALC_A))
    print(f"  insert 반환값: {rid}")

    # Sheets에 기록됐는지
    sheets_rows_a = adapter_a._primary.get_all("calculators", force_refresh=True)
    sheets_a_hit = [r for r in sheets_rows_a if str(r.get("id", "")) == TEST_ID_A]
    check("2A: Sheets에는 기록됨", bool(sheets_a_hit),
          f"Sheets 조회 {len(sheets_a_hit)}건")

    # 재시도 큐에 적재됐는지
    queue_after = list_pending_sync()
    new_items = [i for i in queue_after if i.get("table") == "calculators"
                 and str(i.get("row", {}).get("id", "")) == TEST_ID_A]
    check("2A: 재시도 큐 생성됨", bool(new_items),
          f"큐 대기 수 {queue_count_before} → {len(queue_after)} (+{len(queue_after)-queue_count_before})")
    if new_items:
        qi = new_items[0]
        check("2A: 큐 op=insert", qi.get("op") == "insert", f"op={qi.get('op')}")
        check("2A: 큐 status=pending", qi.get("status") == "pending",
              f"status={qi.get('status')}")

    # 정리: Sheets에서 A 테스트 데이터 삭제
    try:
        adapter_a._primary.delete("calculators", TEST_ID_A)
    except Exception:
        pass

except Exception as e:
    check("2A: insert 예외 없이 완료", False, f"예외: {e}")

# ══════════════════════════════════════════════════════════════
# 2단계 B: Sheets 실패 + Local OK → sync_pending 마킹
# ══════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("2단계 B — Sheets 실패 + Local OK → sync_pending (유실 없음)")
print("=" * 60)

TEST_ID_B = "qa_sync_test_001_B"
TEST_CALC_B = {**TEST_CALC, "id": TEST_ID_B, "slug": "qa-sync-test-001-b"}

adapter_b = DualAdapter(cfg)

def _fail_sheets_insert(table, row):
    raise RuntimeError("QA MOCK: Sheets 강제 실패")

adapter_b._primary.insert = _fail_sheets_insert

print()
print("[2B-1] Sheets 강제 실패 + SQLite OK로 insert 시도")
try:
    rid_b = adapter_b.insert("calculators", dict(TEST_CALC_B))
    print(f"  insert 반환값: {rid_b}")

    # SQLite에 sync_pending으로 기록됐는지
    sqlite_rows_b = adapter_b._secondary.get_all("calculators")
    sqlite_b_hit = [r for r in sqlite_rows_b if str(r.get("id", "")) == TEST_ID_B]
    check("2B: SQLite에 기록됨 (데이터 유실 없음)", bool(sqlite_b_hit),
          f"SQLite 조회 {len(sqlite_b_hit)}건")
    if sqlite_b_hit:
        sb = sqlite_b_hit[0]
        check("2B: sync_status=sync_pending", sb.get("sync_status") == "sync_pending",
              f"sync_status={sb.get('sync_status')}")

    # Sheets에는 기록 안 됐어야 함 (실패했으므로)
    sheets_rows_b = adapter_b._primary.get_all("calculators", force_refresh=True)
    sheets_b_hit = [r for r in sheets_rows_b if str(r.get("id", "")) == TEST_ID_B]
    check("2B: Sheets에는 기록 안 됨 (Sheets 실패 확인)", not bool(sheets_b_hit),
          f"Sheets 조회 {len(sheets_b_hit)}건 (0이어야 함)")

    # 정리: SQLite에서 B 테스트 데이터 삭제
    try:
        adapter_b._secondary.delete("calculators", TEST_ID_B)
    except Exception:
        pass

except Exception as e:
    check("2B: insert 예외 없이 완료", False, f"예외: {e}")


# ══════════════════════════════════════════════════════════════
# 3단계: 테스트 데이터 정리
# ══════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("3단계 — 테스트 데이터 정리")
print("=" * 60)

cleanup_adapter = DualAdapter(cfg)

# qa_sync_test_001 본체 삭제
try:
    cleanup_adapter._primary.delete("calculators", TEST_ID)
    cleanup_adapter._secondary.delete("calculators", TEST_ID)
    print(f"  [정리] {TEST_ID} Sheets + SQLite 삭제 완료")
except Exception as e:
    print(f"  [정리] {TEST_ID} 삭제 중 오류(무해): {e}")

# 큐에서 QA 항목 제거
from adapters.db.dual_adapter import _load_queue, _save_queue
q = _load_queue()
q_cleaned = [i for i in q if not str(i.get("row", {}).get("id", "")).startswith("qa_sync_test_")]
_save_queue(q_cleaned)
removed_count = len(q) - len(q_cleaned)
print(f"  [정리] 동기화 큐 QA 항목 {removed_count}건 제거")

# 최종 검증
print()
final_sheets = cleanup_adapter._primary.get_all("calculators", force_refresh=True)
final_sqlite = cleanup_adapter._secondary.get_all("calculators")
sheets_qa = [r for r in final_sheets if str(r.get("id","")).startswith("qa_sync_test_")]
sqlite_qa = [r for r in final_sqlite if str(r.get("id","")).startswith("qa_sync_test_")]
check("정리 완료: Sheets QA 잔여 없음", len(sheets_qa) == 0,
      f"잔여 {len(sheets_qa)}건")
check("정리 완료: SQLite QA 잔여 없음", len(sqlite_qa) == 0,
      f"잔여 {len(sqlite_qa)}건")


# ══════════════════════════════════════════════════════════════
# 최종 결과
# ══════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("QA-0 최종 결과")
print("=" * 60)
all_pass = all(v == PASS for v in results.values())
for name, status in results.items():
    print(f"  {status}  {name}")
print()
if all_pass:
    print("결론: 전체 PASS ✅ — DB Reset 완료 + Dual Storage 검증 완료")
else:
    fail_items = [k for k, v in results.items() if v != PASS]
    print(f"결론: FAIL ❌ — 실패 항목: {fail_items}")

sys.exit(0 if all_pass else 1)
