"""
adapters/storage/drive_adapter.py — Google Drive 구현체 (현재 기본값)
"""
from pathlib import Path
from google.oauth2.service_account import Credentials
from .base import AbstractStorageAdapter

SCOPES = ["https://www.googleapis.com/auth/drive"]


class DriveAdapter(AbstractStorageAdapter):
    def __init__(self, cfg: dict):
        self._cfg = cfg
        self._svc = None

    def _service(self):
        if self._svc:
            return self._svc
        from googleapiclient.discovery import build
        cred_path = Path(self._cfg.get("_root", ".")) / self._cfg.get(
            "GOOGLE_SERVICE_ACCOUNT_FILE", "credentials.json")
        creds = Credentials.from_service_account_file(str(cred_path), scopes=SCOPES)
        self._svc = build("drive", "v3", credentials=creds)
        return self._svc

    def save_file(self, local_path: Path, remote_name: str, folder: str = "") -> str:
        from googleapiclient.http import MediaFileUpload
        svc = self._service()
        parent = folder or self._cfg.get("GOOGLE_DRIVE_ROOT_ID", "")
        meta = {"name": remote_name}
        if parent:
            meta["parents"] = [parent]
        media = MediaFileUpload(str(local_path), resumable=True)
        f = svc.files().create(body=meta, media_body=media, fields="id").execute()
        fid = f["id"]
        svc.permissions().create(
            fileId=fid, body={"type": "anyone", "role": "reader"}).execute()
        return f"https://drive.google.com/uc?id={fid}"

    def load_file(self, remote_id: str, dest_path: Path):
        from googleapiclient.http import MediaIoBaseDownload
        import io
        svc = self._service()
        req = svc.files().get_media(fileId=remote_id)
        buf = io.BytesIO()
        dl = MediaIoBaseDownload(buf, req)
        done = False
        while not done:
            _, done = dl.next_chunk()
        dest_path.write_bytes(buf.getvalue())

    def delete_file(self, remote_id: str):
        self._service().files().delete(fileId=remote_id).execute()

    def backup_file(self, local_path: Path, backup_folder: str) -> str:
        return self.save_file(local_path, local_path.name, folder=backup_folder)

    def read_test(self) -> bool:
        try:
            self._service().files().list(pageSize=1).execute()
            return True
        except Exception:
            return False
