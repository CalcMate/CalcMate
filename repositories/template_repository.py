"""
repositories/template_repository.py — TemplateRepository (v12.0 재도입)

app_templates 시트(템플릿 저장)용 Repository. App Factory가 사용.
모든 접근은 Adapter 경유(gspread/Drive 직접 호출 금지).

컬럼: template_id, template_name, template_type,
      html_template, seo_template, faq_template, status, created_at
"""
import uuid
from datetime import datetime
from adapters.db.base import AbstractDBAdapter


class TemplateRepository:
    TABLE = "app_templates"

    def __init__(self, db: AbstractDBAdapter):
        self._db = db

    def get_all(self) -> list[dict]:
        return self._db.get_all(self.TABLE)

    def get_active(self) -> list[dict]:
        return self._db.get_where(self.TABLE, {"status": "active"})

    def get_by_type(self, template_type: str) -> list[dict]:
        return self._db.get_where(self.TABLE, {"template_type": template_type})

    def get_by_id(self, template_id: str) -> dict | None:
        rows = self._db.get_where(self.TABLE, {"template_id": template_id})
        return rows[0] if rows else None

    def save(self, tpl: dict) -> str:
        if not tpl.get("template_id"):
            tpl["template_id"] = "tpl_" + datetime.now().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:4]
        tpl.setdefault("status", "active")
        tpl.setdefault("created_at", datetime.now().isoformat())
        return self._db.insert(self.TABLE, tpl)

    def update(self, template_id: str, data: dict):
        self._db.update(self.TABLE, template_id, data)
