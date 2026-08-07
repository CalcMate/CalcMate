import sys
from pathlib import Path
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import json
import os

# 환경 설정
config = {
    'GOOGLE_SERVICE_ACCOUNT_FILE': 'credentials.json',
    '_root': '.',
    'GOOGLE_DRIVE_ROOT_ID': '1b9lmzhybzsmizV8GlRF2pBb_d4a6c0Na'
}

def investigate():
    print("--- DriveAdapter 초기화 검증 시작 ---")
    
    # 1. 파일 존재 확인
    cred_path = Path(config['_root']) / config['GOOGLE_SERVICE_ACCOUNT_FILE']
    print(f"1. Service Account JSON 존재 확인: {'PASS' if cred_path.exists() else 'FAIL'}")

    if not cred_path.exists():
        return

    # 2. JSON 로딩 성공 여부
    try:
        with open(cred_path, 'r') as f:
            json.load(f)
        print("2. JSON 로딩 성공: PASS")
    except Exception as e:
        print(f"2. JSON 로딩 실패: FAIL ({e})")
        return

    # 3. Drive API Service 생성 성공 여부
    try:
        creds = Credentials.from_service_account_file(str(cred_path), scopes=["https://www.googleapis.com/auth/drive"])
        svc = build("drive", "v3", credentials=creds)
        print(f"3. Drive API Service 생성: PASS (Type: {type(svc)})")
    except Exception as e:
        print(f"3. Drive API Service 생성 실패: FAIL ({e})")
        return

    # 4. Folder ID 접근 성공 여부
    folder_id = config['GOOGLE_DRIVE_ROOT_ID']
    try:
        res = svc.files().get(fileId=folder_id, fields="id, name").execute()
        print(f"4. Folder ID 접근 성공: PASS (Folder: {res['name']})")
    except Exception as e:
        print(f"4. Folder ID 접근 실패: FAIL ({e})")
        return

    # 5. save_file() 단독 테스트
    test_file = Path("test_upload.txt")
    test_file.write_text("test content", encoding="utf-8")
    try:
        meta = {"name": "test_upload.txt", "parents": [folder_id]}
        media = MediaFileUpload(str(test_file), mimetype='text/plain')
        f = svc.files().create(body=meta, media_body=media, fields="id").execute()
        print(f"5. save_file() 테스트 성공: PASS (File ID: {f['id']})")
        
        # Cleanup
        svc.files().delete(fileId=f['id']).execute()
        test_file.unlink()
    except Exception as e:
        print(f"5. save_file() 테스트 실패: FAIL ({e})")
        if test_file.exists(): test_file.unlink()

if __name__ == "__main__":
    investigate()
