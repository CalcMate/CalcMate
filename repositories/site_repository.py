"""
repositories/site_repository.py — SiteRepository
sites 테이블 CRUD + secrets.yaml WP/AI 프로필 조회
"""
import uuid
from datetime import datetime
from pathlib import Path
import yaml
from adapters.db.base import AbstractDBAdapter


class SiteRepository:
    TABLE = "sites"

    def __init__(self, db: AbstractDBAdapter, cfg: dict):
        self._db = db
        self._cfg = cfg
        self._secrets = self._load_secrets(cfg)

    @staticmethod
    def _load_secrets(cfg: dict) -> dict:
        root = Path(cfg.get("_root", "."))
        p = root / "config" / "secrets.yaml"
        if p.exists():
            with open(p, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    # ── 조회 ──────────────────────────────────────────────────
    def get_active_sites(self) -> list[dict]:
        return self._db.get_where(self.TABLE, {"status": "active"})

    def get_by_id(self, site_id: str) -> dict | None:
        rows = self._db.get_where(self.TABLE, {"site_id": site_id})
        return rows[0] if rows else None

    def get_by_type(self, site_type: str) -> list[dict]:
        return self._db.get_where(self.TABLE, {"site_type": site_type})

    def get_all(self) -> list[dict]:
        return self._db.get_all(self.TABLE)

    # ── 보안: WP 계정 조회 (secrets.yaml) ────────────────────
    def get_wp_config(self, site_id: str) -> dict:
        site = self.get_by_id(site_id)
        if not site:
            return {}
        profile_id = site.get("wordpress_profile_id", "")
        profiles = self._secrets.get("wordpress_profiles", {})
        profile = profiles.get(profile_id, {})
        return {
            "WORDPRESS_URL":          profile.get("url", site.get("wordpress_url", "")),
            "WORDPRESS_USERNAME":     profile.get("username", ""),
            "WORDPRESS_APP_PASSWORD": profile.get("app_password", ""),
        }

    # ── AI 모델 조회 ──────────────────────────────────────────
    def get_ai_config(self, site_id: str) -> dict:
        site = self.get_by_id(site_id) or {}
        ai_keys = self._secrets.get("ai_keys", {})
        def _key(profile: str) -> str:
            return ai_keys.get(profile, self._cfg.get(
                {"gemini_flash": "GEMINI_API_KEY",
                 "gpt4o": "OPENAI_API_KEY",
                 "claude_sonnet": "ANTHROPIC_API_KEY",
                 "claude_haiku": "ANTHROPIC_API_KEY"}.get(profile, ""), ""))
        return {
            "research_ai":  site.get("research_ai", "gemini_flash"),
            "writing_ai":   site.get("writing_ai",  "gpt4o"),
            "review_ai":    site.get("review_ai",   "claude_sonnet"),
            "research_key": _key(site.get("research_ai", "gemini_flash")),
            "writing_key":  _key(site.get("writing_ai",  "gpt4o")),
            "review_key":   _key(site.get("review_ai",   "claude_sonnet")),
        }

    # ── 쓰기 ──────────────────────────────────────────────────
    def save(self, site: dict) -> str:
        if not site.get("site_id"):
            site["site_id"] = "site_" + datetime.now().strftime("%Y%m%d%H%M%S")
        if not site.get("created_at"):
            site["created_at"] = datetime.now().isoformat()
        site.setdefault("status", "active")
        return self._db.insert(self.TABLE, site)

    def update_status(self, site_id: str, status: str):
        self._db.update(self.TABLE, site_id, {"status": status})

    def update(self, site_id: str, data: dict):
        self._db.update(self.TABLE, site_id, data)

    def delete(self, site_id: str):
        self._db.delete(self.TABLE, site_id)

    # ── secrets.yaml WP 프로필 저장 (앱 비밀번호는 시트가 아닌 로컬 보안 파일) ──
    def save_wp_profile(self, profile_id: str, url: str, username: str, app_password: str):
        root = Path(self._cfg.get("_root", "."))
        p = root / "config" / "secrets.yaml"
        data = {}
        if p.exists():
            with open(p, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        data.setdefault("wordpress_profiles", {})
        data["wordpress_profiles"][profile_id] = {
            "url": url, "username": username, "app_password": app_password,
        }
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        self._secrets = data
