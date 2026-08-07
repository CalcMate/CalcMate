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

def audit_error():
    print("--- 403 오류 심층 조사 시작 ---")
    cred_path = Path(config['_root']) / config['GOOGLE_SERVICE_ACCOUNT_FILE']
    creds = Credentials.from_service_account_file(str(cred_path), scopes=["https://www.googleapis.com/auth/drive"])
    svc = build("drive", "v3", credentials=creds)
    
    folder_id = config['GOOGLE_DRIVE_ROOT_ID']
    
    # 403 오류 발생 시 전체 response body 캡처
    remote_name = "test_audit_403.txt"
    meta = {"name": remote_name, "parents": [folder_id]}
    
    try:
        # 실제 생성 시도
        res = svc.files().create(body=meta).execute()
        print(f"생성 성공: {res}")
    except Exception as e:
        print("--- 6. 403 오류 응답 전문 ---")
        if hasattr(e, 'resp'):
            print(f"Status: {e.resp.status}")
        if hasattr(e, 'content'):
            print(f"Content: {e.content.decode('utf-8')}")
        else:
            print(f"Exception: {e}")

if __name__ == "__main__":
    audit_error()
