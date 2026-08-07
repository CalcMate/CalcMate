from pathlib import Path
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import json

# 환경 설정
config = {
    'GOOGLE_SERVICE_ACCOUNT_FILE': 'credentials.json',
    '_root': '.',
    'GOOGLE_DRIVE_ROOT_ID': '1b9lmzhybzsmizV8GlRF2pBb_d4a6c0Na'
}

def audit():
    print("--- DriveAudit 시작 ---")
    cred_path = Path(config['_root']) / config['GOOGLE_SERVICE_ACCOUNT_FILE']
    creds = Credentials.from_service_account_file(str(cred_path), scopes=["https://www.googleapis.com/auth/drive"])
    svc = build("drive", "v3", credentials=creds)
    
    folder_id = config['GOOGLE_DRIVE_ROOT_ID']
    
    # 4. Folder ID 조사
    try:
        folder = svc.files().get(fileId=folder_id, fields="id, name, kind, driveId").execute()
        print(f"4. Folder Info: {folder}")
    except Exception as e:
        print(f"4. Folder 접근 실패: {e}")
        return

    # 2. metadata 조사
    remote_name = "test_audit.txt"
    meta = {"name": remote_name, "parents": [folder_id]}
    print(f"2. files().create metadata: {meta}")

    # 6. 오류 전문 조사
    try:
        # 실제 생성 시도
        svc.files().create(body=meta).execute()
    except Exception as e:
        print(f"6. 403 오류 전문: {e}")

if __name__ == "__main__":
    audit()
