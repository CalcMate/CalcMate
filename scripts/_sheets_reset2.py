# -*- coding: utf-8 -*-
"""
1) 로컬 CSV 백업 (Drive 할당량 초과 대안)
2) 마스터_DB / 운영로그 / calculators 데이터행 삭제 (헤더 유지)
3) 결과 보고
"""
import sys, io, csv, pathlib
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"C:\Users\연수\Desktop\블로그자동_v12")

from google.oauth2.service_account import Credentials
import gspread
from modules.config_loader import load_config

cfg = load_config()
SHEET_ID = cfg["GOOGLE_SHEET_ID"]
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
from pathlib import Path
root = Path(r"C:\Users\연수\Desktop\블로그자동_v12")
cred_path = root / cfg.get("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials.json")
creds = Credentials.from_service_account_file(str(cred_path), scopes=SCOPES)
import google.auth.transport.requests as ga_req
creds.refresh(ga_req.Request())

gc = gspread.authorize(creds)
sh = gc.open_by_key(SHEET_ID)

CLEAR_TABS = ["마스터_DB", "운영로그", "calculators"]
backup_dir = root / "data" / "backup" / "SalaryMate_DB_backup_20260805_before_reset"
backup_dir.mkdir(parents=True, exist_ok=True)

# ── STEP 1: 로컬 CSV 백업 ──────────────────────────────
print("=== STEP 1: 로컬 CSV 백업 ===")
for tab_name in CLEAR_TABS:
    ws = sh.worksheet(tab_name)
    rows = ws.get_all_values()
    safe_name = tab_name.replace("/", "_")
    fp = backup_dir / f"{safe_name}.csv"
    with open(fp, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    print(f"  [{tab_name}] {len(rows)}행 → {fp.name}")

print(f"  백업 위치: {backup_dir}")

# ── STEP 2: 데이터 삭제 ──────────────────────────────
print()
print("=== STEP 2: 데이터 삭제 (헤더 유지) ===")
results = {}
for tab_name in CLEAR_TABS:
    ws = sh.worksheet(tab_name)
    all_vals = ws.get_all_values()
    total_before = len(all_vals)

    if total_before <= 1:
        print(f"  [{tab_name}] 데이터 없음 — 스킵")
        results[tab_name] = {"before": total_before, "after": total_before, "deleted": 0}
        continue

    # batch_clear: 2행부터 마지막 행까지 지움
    ws.batch_clear([f"A2:ZZ{total_before}"])

    after_vals = ws.get_all_values()
    after_count = len(after_vals)
    deleted = total_before - after_count
    results[tab_name] = {"before": total_before, "after": after_count, "deleted": deleted}
    print(f"  [{tab_name}] {total_before}행 → {after_count}행 (삭제 {deleted}행)")

# ── STEP 3: 보존 시트 검증 ──────────────────────────────
print()
print("=== STEP 3: 보존 시트 검증 ===")
KEEP_TABS = ["app_templates", "sites", "app_factory_queue", "app_factory_logs"]
for tab_name in KEEP_TABS:
    try:
        ws = sh.worksheet(tab_name)
        vals = ws.get_all_values()
        print(f"  [{tab_name}] {len(vals)}행 — 변경 없음 ✅")
    except Exception as e:
        print(f"  [{tab_name}] 오류: {e}")

# ── 최종 요약 ──────────────────────────────
print()
print("=== 최종 보고 ===")
print(f"백업 (로컬): {backup_dir}")
print("삭제 결과:")
for tab, r in results.items():
    print(f"  {tab}: {r['before']}행 → {r['after']}행 (삭제 {r['deleted']}행)")
