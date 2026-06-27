"""
modules/backup_manager.py — 통합 백업 매니저
역할: Sheets CSV / Drive 파일 / 로컬 outputs / SQLite DB 덤프
      → /backups/YYYY-MM-DD.zip 으로 압축 보관

사용:
    from modules.backup_manager import BackupManager
    bm = BackupManager(cfg)
    bm.run_daily_backup()
"""
import csv
import io
import json
import shutil
import zipfile
from datetime import datetime, timedelta
from pathlib import Path


BACKUP_DIR = Path("backups")
KEEP_DAYS  = 30   # 보관 일수


class BackupManager:
    def __init__(self, cfg: dict):
        self._cfg  = cfg
        self._root = Path(cfg.get("_root", "."))
        self._backup_dir = self._root / "backups"
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    # ── 메인 진입점 ───────────────────────────────────────────
    def run_daily_backup(self) -> Path:
        """오늘 날짜 zip 백업 생성 후 경로 반환"""
        today = datetime.now().strftime("%Y-%m-%d")
        zip_path = self._backup_dir / f"{today}.zip"

        with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
            self._backup_config(zf)
            self._backup_sheets(zf)
            self._backup_sqlite(zf)
            self._backup_outputs(zf)

        self._delete_old_backups()
        print(f"[BackupManager] 백업 완료: {zip_path}")
        return zip_path

    # ── 설정 파일 백업 ────────────────────────────────────────
    def _backup_config(self, zf: zipfile.ZipFile):
        config_dir = self._root / "config"
        for f in config_dir.glob("*.yaml"):
            if "secrets" in f.name:
                continue  # secrets.yaml 제외 (보안)
            zf.write(str(f), f"config/{f.name}")

    # ── Google Sheets CSV 백업 ────────────────────────────────
    def _backup_sheets(self, zf: zipfile.ZipFile):
        adapter_type = self._cfg.get("DB_ADAPTER", "sheets")
        if adapter_type != "sheets":
            return
        try:
            from adapters.db.factory import get_db_adapter
            db = get_db_adapter(self._cfg)
            tables = [
                "articles", "sites", "calculators",
                "app_templates", "app_factory_queue",
            ]
            for table in tables:
                try:
                    rows = db.get_all(table)
                    if not rows:
                        continue
                    buf = io.StringIO()
                    writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows(rows)
                    zf.writestr(f"sheets/{table}.csv", buf.getvalue())
                except Exception as e:
                    print(f"[BackupManager] {table} CSV 실패: {e}")
        except Exception as e:
            print(f"[BackupManager] Sheets 백업 실패: {e}")

    # ── SQLite DB 덤프 ────────────────────────────────────────
    def _backup_sqlite(self, zf: zipfile.ZipFile):
        adapter_type = self._cfg.get("DB_ADAPTER", "sheets")
        if adapter_type != "sqlite":
            return
        try:
            from adapters.db.factory import get_db_adapter
            db = get_db_adapter(self._cfg)
            if hasattr(db, "dump"):
                tmp = self._backup_dir / "_tmp_dump.db"
                db.dump(tmp)
                zf.write(str(tmp), "sqlite/blog_auto.db")
                tmp.unlink(missing_ok=True)
        except Exception as e:
            print(f"[BackupManager] SQLite 덤프 실패: {e}")

    # ── 로컬 outputs 백업 ─────────────────────────────────────
    def _backup_outputs(self, zf: zipfile.ZipFile):
        outputs_dir = self._root / "data" / "outputs"
        if not outputs_dir.exists():
            return
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        for f in outputs_dir.glob(f"{yesterday}_*.txt"):
            zf.write(str(f), f"outputs/{f.name}")

    # ── 오래된 백업 삭제 ──────────────────────────────────────
    def _delete_old_backups(self):
        cutoff = datetime.now() - timedelta(days=KEEP_DAYS)
        for f in self._backup_dir.glob("*.zip"):
            try:
                date_str = f.stem  # "2026-06-19"
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                if file_date < cutoff:
                    f.unlink()
                    print(f"[BackupManager] 오래된 백업 삭제: {f.name}")
            except ValueError:
                # 파일명이 YYYY-MM-DD.zip 형식이 아니면 백업 파일이 아니므로 스킵
                print(f"[BackupManager] 백업 형식 아님 — 스킵: {f.name}")

    # ── Storage Adapter로 원격 백업 ───────────────────────────
    def upload_to_storage(self, zip_path: Path) -> str:
        """생성된 zip을 Storage Adapter로 업로드 (Drive/Local/S3)"""
        try:
            from adapters.storage.factory import get_storage_adapter
            storage = get_storage_adapter(self._cfg)
            backup_folder = self._cfg.get("BACKUP_STORAGE_FOLDER", "backups")
            url = storage.backup_file(zip_path, backup_folder)
            print(f"[BackupManager] 원격 백업 완료: {url}")
            return url
        except Exception as e:
            print(f"[BackupManager] 원격 업로드 실패 (로컬 백업은 유지): {e}")
            return ""

    def compress_yesterday(self):
        """main.py 스케줄 모드에서 호출하는 하위 호환 메서드"""
        self.run_daily_backup()

    def delete_old_backups(self):
        """main.py 스케줄 모드에서 호출하는 하위 호환 메서드"""
        self._delete_old_backups()
