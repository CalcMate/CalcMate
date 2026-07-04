"""
modules/google_provisioner.py — Google Sheets / Drive 자동 생성
Setup Wizard 2단계에서 호출.

생성 항목:
  Drive: blog_auto_v12/ (루트)
           ├─ images/
           ├─ backups/
           └─ placeholders/
  Sheets: 블로그자동화_v12
           ├─ 마스터_DB
           ├─ 운영로그
           ├─ sites
           ├─ calculators
           ├─ app_templates
           ├─ app_factory_queue
           └─ app_factory_logs
"""
from pathlib import Path
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ── 탭 헤더 정의 ──────────────────────────────────────────────────────────────
SHEET_TABS = {
    "마스터_DB": [
        "ID", "site_id", "상태값", "정책명", "최종추천제목",
        "메인 키워드", "메타설명", "태그", "발행 URL", "발행일시",
        "원본출처", "우선발행점수", "최종수정일", "상태변경로그",
        "wp_post_id", "wp_permalink", "wp_status", "published_at", "history",
    ],
    "운영로그": [
        "로그ID", "실행일시", "마스터ID", "대상정책명", "가동결과",
        "실패모듈", "오류내용", "발행URL", "소요시간", "토큰합계",
    ],
    "sites": [
        "site_id", "site_name", "domain", "site_type", "monetization_type",
        "wordpress_url", "wordpress_profile_id", "rss_sources",
        "content_mode", "research_ai", "writing_ai", "review_ai",
        "publish_mode", "site_tags", "site_priority", "status", "created_at",
    ],
    "calculators": [
        "id", "name", "slug", "category", "calculator_type",
        "template_id", "version", "published_url", "site_id",
        "formula", "faq", "input_schema", "output_schema",
        "seo_title", "seo_desc", "status", "created_at", "updated_at",
    ],
    "app_templates": [
        "template_id", "template_name", "template_type",
        "html_template", "seo_template", "faq_template",
        "status", "created_at",
    ],
    "app_factory_queue": [
        "job_id", "job_type", "input_data", "ai_engine",
        "template_id", "status", "created_at", "updated_at",
    ],
    "app_factory_logs": [
        "log_id", "job_id", "step", "result", "created_at",
    ],
}

# 탭 생성 순서 (첫 번째 탭이 기본 시트)
TAB_ORDER = [
    "마스터_DB", "운영로그", "sites", "calculators",
    "app_templates", "app_factory_queue", "app_factory_logs",
]


def provision(creds_path: str) -> dict:
    """
    반환:
      sheet_id, sheet_url,
      drive_root_id, images_folder_id,
      placeholders_folder_id (= placeholder_folder_id),
      backups_folder_id
    """
    creds   = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    drive   = build("drive",        "v3", credentials=creds)
    sheets  = build("sheets",       "v4", credentials=creds)

    # ── 1. Drive 폴더 생성 ────────────────────────────────────
    root_id          = _make_drive_folder(drive, "blog_auto_v12")
    images_id        = _make_drive_folder(drive, "images",       root_id)
    backups_id       = _make_drive_folder(drive, "backups",      root_id)
    placeholders_id  = _make_drive_folder(drive, "placeholders", root_id)

    # 폴더 공개 읽기 권한 (이미지 직접 URL 사용 시 필요)
    _make_public(drive, images_id)

    # ── 2. Spreadsheet 생성 ───────────────────────────────────
    ss = sheets.spreadsheets().create(body={
        "properties": {"title": "블로그자동화_v12"},
        "sheets": [{"properties": {"title": TAB_ORDER[0]}}],
    }).execute()
    sheet_id  = ss["spreadsheetId"]
    sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}"

    # ── 3. 나머지 탭 추가 ─────────────────────────────────────
    requests = []
    for tab in TAB_ORDER[1:]:
        requests.append({"addSheet": {"properties": {"title": tab}}})
    if requests:
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": requests},
        ).execute()

    # ── 4. 헤더 행 기록 ──────────────────────────────────────
    data = []
    for tab in TAB_ORDER:
        headers = SHEET_TABS[tab]
        data.append({
            "range": f"'{tab}'!A1",
            "values": [headers],
        })
    sheets.spreadsheets().values().batchUpdate(
        spreadsheetId=sheet_id,
        body={"valueInputOption": "RAW", "data": data},
    ).execute()

    # ── 5. 헤더 행 굵게 + 배경색 ─────────────────────────────
    _format_headers(sheets, sheet_id, ss["sheets"])
    # 탭 추가 후 시트 목록 재조회
    ss_info = sheets.spreadsheets().get(spreadsheetId=sheet_id).execute()
    _format_headers(sheets, sheet_id, ss_info["sheets"])

    # ── 6. Spreadsheet Drive 권한 (서비스 계정 본인 소유라 기본 OK) ──
    # 개인 구글 계정에서도 볼 수 있도록 편집자 공유 (선택)
    # drive.permissions().create(fileId=sheet_id, body={"type":"anyone","role":"writer"}).execute()

    return {
        "sheet_id":              sheet_id,
        "sheet_url":             sheet_url,
        "drive_root_id":         root_id,
        "images_folder_id":      images_id,
        "placeholder_folder_id": placeholders_id,
        "placeholders_folder_id":placeholders_id,
        "backups_folder_id":     backups_id,
    }


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────
def _make_drive_folder(drive, name: str, parent_id: str = None) -> str:
    meta = {
        "name":     name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        meta["parents"] = [parent_id]
    f = drive.files().create(body=meta, fields="id").execute()
    return f["id"]


def _make_public(drive, file_id: str):
    drive.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()


def _format_headers(sheets, sheet_id: str, sheets_list: list):
    """헤더 행: 굵게 + 하늘색 배경 + 열 고정"""
    requests = []
    for sheet in sheets_list:
        sid  = sheet["properties"]["sheetId"]
        tab  = sheet["properties"]["title"]
        cols = len(SHEET_TABS.get(tab, []))
        if cols == 0:
            continue
        requests += [
            # 굵게 + 배경색
            {"repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1,
                          "startColumnIndex": 0, "endColumnIndex": cols},
                "cell": {"userEnteredFormat": {
                    "textFormat": {"bold": True},
                    "backgroundColor": {"red": 0.78, "green": 0.87, "blue": 0.95},
                }},
                "fields": "userEnteredFormat(textFormat,backgroundColor)",
            }},
            # 첫 행 고정
            {"updateSheetProperties": {
                "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 1}},
                "fields": "gridProperties.frozenRowCount",
            }},
        ]
    if requests:
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": requests},
        ).execute()
