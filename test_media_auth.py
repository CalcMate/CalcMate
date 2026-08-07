import requests
from requests.auth import HTTPBasicAuth
from pathlib import Path
import sys

# 테스트 설정 (기존 publisher.py와 동일한 설정 활용)
url = "http://salarymate.test/wp-json/wp/v2/media"
username = "geminia"
app_password = "Qdjz ZzYU Cp24 3csx VSHV 0szD" # secrets.yaml에서 확인한 값
test_file = Path("test_upload.txt")
test_file.write_text("test content", encoding="utf-8")

def test_upload():
    print(f"--- 단독 업로드 테스트 ---")
    print(f"URL: {url}")
    print(f"Auth: {username} / {'*' * len(app_password)}")
    
    headers = {"Content-Disposition": f"attachment; filename={test_file.name}"}
    
    try:
        with open(test_file, "rb") as f:
            resp = requests.post(
                url, data=f, headers=headers,
                auth=HTTPBasicAuth(username, app_password),
                timeout=30,
            )
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}")
    except Exception as e:
        print(f"Exception: {e}")
    finally:
        if test_file.exists():
            test_file.unlink()

if __name__ == "__main__":
    test_upload()
