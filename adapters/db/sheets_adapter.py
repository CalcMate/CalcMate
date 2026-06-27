"""
adapters/db/sheets_adapter.py — Google Sheets 구현체 (현재 기본값)
"""
import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path
from datetime import datetime
from .base import AbstractDBAdapter

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# 테이블명 → Sheets 탭명 매핑
_TAB = {
    "sites":              "sites",
    "articles":           "마스터_DB",
    "logs":               "운영로그",
    "calculators":        "calculators",
    "app_templates":      "app_templates",
    "app_factory_queue":  "app_factory_queue",
    "app_factory_logs":   "app_factory_logs",
}

# 테이블별 id 컬럼명
_ID_COL = {
    "sites":             "site_id",
    "articles":          "ID",
    "calculators":       "id",
    "app_templates":     "template_id",
    "app_factory_queue": "job_id",
    "app_factory_logs":  "log_id",
}


class SheetsAdapter(AbstractDBAdapter):
    def __init__(self, cfg: dict):
        self._cfg = cfg
        self._gc = None
        self._sh = None

    def _connect(self):
        if self._gc:
            return
        root = Path(self._cfg.get("_root", "."))
        cred_path = root / self._cfg.get("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials.json")
        creds = Credentials.from_service_account_file(str(cred_path), scopes=SCOPES)
        self._gc = gspread.authorize(creds)
        self._sh = self._gc.open_by_key(self._cfg["GOOGLE_SHEET_ID"])

    def _ws(self, table: str):
        self._connect()
        tab = _TAB.get(table, table)
        try:
            return self._sh.worksheet(tab)
        except gspread.WorksheetNotFound:
            ws = self._sh.add_worksheet(tab, rows=1000, cols=50)
            return ws

    # ── CRUD ──────────────────────────────────────────────────
    def get_all(self, table: str) -> list[dict]:
        return self._ws(table).get_all_records(head=1)

    def get_where(self, table: str, filters: dict) -> list[dict]:
        rows = self.get_all(table)
        for col, val in filters.items():
            rows = [r for r in rows if str(r.get(col, "")) == str(val)]
        return rows

    def insert(self, table: str, row: dict) -> str:
        ws = self._ws(table)
        headers = ws.row_values(1)
        if not headers:
            headers = list(row.keys())
            ws.update("A1", [headers])
        values = [str(row.get(h, "") or "") for h in headers]
        ws.append_row(values, value_input_option="USER_ENTERED")
        id_col = _ID_COL.get(table, "id")
        return str(row.get(id_col, ""))

    def update(self, table: str, row_id: str, data: dict):
        ws = self._ws(table)
        all_vals = ws.get_all_values()
        if not all_vals:
            return
        headers = all_vals[0]
        # 신규 컬럼은 헤더에 자동 추가(기존 컬럼/데이터 불변)
        missing = [c for c in data.keys() if c not in headers]
        if missing:
            headers = headers + missing
            ws.update("A1", [headers])
        id_col = _ID_COL.get(table, "id")
        id_idx = headers.index(id_col) if id_col in headers else 0
        for i, row in enumerate(all_vals[1:], start=2):
            if str(row[id_idx]) == str(row_id):
                for col, val in data.items():
                    if col in headers:
                        ws.update_cell(i, headers.index(col) + 1, str(val or ""))
                ws.update_cell(i, headers.index("updated_at") + 1,
                               datetime.now().isoformat()) if "updated_at" in headers else None
                return

    def delete(self, table: str, row_id: str):
        ws = self._ws(table)
        all_vals = ws.get_all_values()
        if not all_vals:
            return
        headers = all_vals[0]
        id_col = _ID_COL.get(table, "id")
        id_idx = headers.index(id_col) if id_col in headers else 0
        for i, row in enumerate(all_vals[1:], start=2):
            if str(row[id_idx]) == str(row_id):
                ws.delete_rows(i)
                return

    def read_test(self) -> bool:
        try:
            self._connect()
            self._sh.worksheets()
            return True
        except Exception:
            return False
