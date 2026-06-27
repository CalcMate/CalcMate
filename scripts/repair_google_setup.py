# -*- coding: utf-8 -*-
"""
scripts/repair_google_setup.py — 기존 Google Sheet/Drive 구조 보수(멱등)

위저드 자동생성이 완료되지 않아 탭/폴더가 일부만 만들어진 경우 사용.
- 기존 리소스(config.yaml의 GOOGLE_SHEET_ID / GOOGLE_DRIVE_ROOT_ID)를 재사용
- 누락된 탭만 추가, 헤더가 비어있는 탭에만 헤더 기록 (데이터 있는 탭은 절대 건드리지 않음)
- images/backups/placeholders 하위 폴더가 없으면 생성
- GOOGLE_DRIVE_PLACEHOLDER_FOLDER_ID 가 루트와 같거나 비어있으면 실제 placeholders 폴더로 교정

실행:  .venv\\Scripts\\python.exe scripts\\repair_google_setup.py
"""
import io
import sys
from pathlib import Path

import yaml

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from modules.google_provisioner import (
    SHEET_TABS, TAB_ORDER, SCOPES,
    _make_drive_folder, _make_public, _format_headers,
)

CFG_PATH = BASE / "config" / "config.yaml"


def _load_cfg() -> dict:
    with open(CFG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_cfg(cfg: dict):
    with open(CFG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def repair():
    cfg = _load_cfg()
    creds_path = BASE / cfg.get("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials.json")
    sheet_id = cfg.get("GOOGLE_SHEET_ID", "")
    root_id = cfg.get("GOOGLE_DRIVE_ROOT_ID", "")

    if not creds_path.exists():
        print(f"[중단] 서비스 계정 파일 없음: {creds_path}")
        return
    if not sheet_id or not root_id:
        print("[중단] config.yaml 에 GOOGLE_SHEET_ID / GOOGLE_DRIVE_ROOT_ID 가 없습니다.")
        return

    creds = Credentials.from_service_account_file(str(creds_path), scopes=SCOPES)
    drive = build("drive", "v3", credentials=creds)
    sheets = build("sheets", "v4", credentials=creds)

    # ── 1. Sheet 탭 보수 ──────────────────────────────────────
    ss = sheets.spreadsheets().get(spreadsheetId=sheet_id).execute()
    existing = [s["properties"]["title"] for s in ss["sheets"]]
    print(f"[Sheet] 현재 탭: {existing}")

    add_reqs = [{"addSheet": {"properties": {"title": t}}}
                for t in TAB_ORDER if t not in existing]
    if add_reqs:
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id, body={"requests": add_reqs}).execute()
        added = [r["addSheet"]["properties"]["title"] for r in add_reqs]
        print(f"[Sheet] 탭 추가: {added}")
    else:
        print("[Sheet] 추가할 탭 없음")

    # 헤더가 비어있는 탭에만 헤더 기록 (데이터 보존)
    header_data = []
    for tab in TAB_ORDER:
        r = sheets.spreadsheets().values().get(
            spreadsheetId=sheet_id, range=f"'{tab}'!A1:A1").execute()
        if not r.get("values"):  # A1 비어있음 → 헤더 없음
            header_data.append({"range": f"'{tab}'!A1", "values": [SHEET_TABS[tab]]})
    if header_data:
        sheets.spreadsheets().values().batchUpdate(
            spreadsheetId=sheet_id,
            body={"valueInputOption": "RAW", "data": header_data}).execute()
        print(f"[Sheet] 헤더 기록(빈 탭): {[d['range'] for d in header_data]}")
    else:
        print("[Sheet] 헤더 기록 불필요(모든 탭에 헤더 존재)")

    # 헤더 서식
    ss_info = sheets.spreadsheets().get(spreadsheetId=sheet_id).execute()
    _format_headers(sheets, sheet_id, ss_info["sheets"])
    print("[Sheet] 헤더 서식 적용 완료")

    # ── 2. Drive 하위 폴더 보수 ───────────────────────────────
    ch = drive.files().list(
        q=f"'{root_id}' in parents and trashed=false "
          f"and mimeType='application/vnd.google-apps.folder'",
        fields="files(id,name)").execute().get("files", [])
    by_name = {c["name"]: c["id"] for c in ch}
    print(f"[Drive] 현재 하위 폴더: {list(by_name.keys())}")

    folder_ids = {}
    for name in ("images", "backups", "placeholders"):
        if name in by_name:
            folder_ids[name] = by_name[name]
            print(f"[Drive] '{name}' 이미 존재")
        else:
            folder_ids[name] = _make_drive_folder(drive, name, root_id)
            print(f"[Drive] '{name}' 생성 → {folder_ids[name]}")

    # images 공개 읽기
    try:
        _make_public(drive, folder_ids["images"])
        print("[Drive] images 폴더 공개 읽기 권한 적용")
    except Exception as e:
        print(f"[Drive] images 공개 권한 경고(무시 가능): {e}")

    # ── 3. config.yaml 교정 ───────────────────────────────────
    changed = False
    ph_now = cfg.get("GOOGLE_DRIVE_PLACEHOLDER_FOLDER_ID", "")
    if ph_now in ("", root_id):  # 비어있거나 루트와 동일하면 교정
        cfg["GOOGLE_DRIVE_PLACEHOLDER_FOLDER_ID"] = folder_ids["placeholders"]
        changed = True
        print(f"[config] PLACEHOLDER_FOLDER_ID → {folder_ids['placeholders']}")
    if changed:
        _save_cfg(cfg)
        print("[config] config.yaml 저장 완료")
    else:
        print("[config] 변경 없음")

    print("\n✅ 보수 완료")
    print(f"   Sheet : https://docs.google.com/spreadsheets/d/{sheet_id}")
    print(f"   Drive : https://drive.google.com/drive/folders/{root_id}")


if __name__ == "__main__":
    repair()
