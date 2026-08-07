# -*- coding: utf-8 -*-
"""
1) 스프레드시트 사본 생성 (Google Drive API)
2) 마스터_DB / 운영로그 / calculators 데이터행 삭제 (헤더 유지)
3) 결과 보고
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"C:\Users\연수\Desktop\블로그자동_v12")

from pathlib import Path
from google.oauth2.service_account import Credentials
import gspread, requests

from modules.config_loader import load_config

cfg = load_config()
SHEET_ID = cfg["GOOGLE_SHEET_ID"]
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
root = Path(cfg.get("_root", "."))
cred_path = root / cfg.get("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials.json")
creds = Credentials.from_service_account_file(str(cred_path), scopes=SCOPES)

# ── STEP 1: Drive API로 사본 생성 ──────────────────────────────
print("=== STEP 1: 사본 생성 ===")
BACKUP_NAME = "SalaryMate_DB_backup_20260805_before_reset"
drive_url = f"https://www.googleapis.com/drive/v3/files/{SHEET_ID}/copy"
token = creds.token
# 토큰 갱신
import google.auth.transport.requests as ga_req
creds.refresh(ga_req.Request())
headers = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}
resp = requests.post(drive_url, headers=headers, json={"name": BACKUP_NAME})
if resp.status_code in (200, 201):
    backup_id = resp.json().get("id", "")
    print(f"  사본 생성 완료: {BACKUP_NAME}")
    print(f"  사본 ID: {backup_id}")
else:
    print(f"  사본 생성 실패: {resp.status_code} {resp.text[:200]}")
    sys.exit(1)

# ── STEP 2: 원본 시트 데이터 삭제 ──────────────────────────────
print()
print("=== STEP 2: 데이터 삭제 (헤더 유지) ===")
gc = gspread.authorize(creds)
sh = gc.open_by_key(SHEET_ID)

CLEAR_TABS = ["마스터_DB", "운영로그", "calculators"]
KEEP_TABS  = ["app_templates", "sites", "app_factory_queue", "app_factory_logs"]

results = {}
for tab_name in CLEAR_TABS:
    try:
        ws = sh.worksheet(tab_name)
        all_vals = ws.get_all_values()
        total_before = len(all_vals)
        
        if total_before <= 1:
            print(f"  [{tab_name}] 데이터 없음 (헤더만 또는 빈 시트) — 스킵")
            results[tab_name] = {"before": total_before, "after": 1, "deleted": 0}
            continue
        
        # 2행부터 끝까지 삭제: 범위 "A2:ZZ{total_before}"
        last_row = total_before
        ws.batch_clear([f"A2:ZZ{last_row}"])
        
        # 확인
        after_vals = ws.get_all_values()
        after_count = len(after_vals)
        deleted = total_before - after_count
        results[tab_name] = {"before": total_before, "after": after_count, "deleted": deleted}
        print(f"  [{tab_name}] {total_before}행 → {after_count}행 (삭제 {deleted}행)")
    except Exception as e:
        print(f"  [{tab_name}] 오류: {e}")
        results[tab_name] = {"error": str(e)}

# 보존 시트 확인
print()
print("=== STEP 3: 보존 시트 확인 ===")
for tab_name in KEEP_TABS:
    try:
        ws = sh.worksheet(tab_name)
        vals = ws.get_all_values()
        print(f"  [{tab_name}] {len(vals)}행 (변경 없음)")
    except Exception as e:
        print(f"  [{tab_name}] 오류: {e}")

print()
print("=== 최종 보고 ===")
print(f"사본: {BACKUP_NAME}")
print(f"사본 ID: {backup_id}")
for tab, r in results.items():
    if "error" in r:
        print(f"  {tab}: 오류 — {r['error']}")
    else:
        print(f"  {tab}: {r['before']}행 → {r['after']}행 (삭제 {r['deleted']}행)")
