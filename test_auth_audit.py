import requests
from requests.auth import HTTPBasicAuth
from pathlib import Path
import sys

# 테스트 설정 (기존 publisher.py와 동일한 설정 활용)
url_posts = "http://salarymate.test/wp-json/wp/v2/posts"
url_media = "http://salarymate.test/wp-json/wp/v2/media"
username = "geminia"
app_password = "Qdjz ZzYU Cp24 3csx VSHV 0szD" # secrets.yaml 값

def test_auth():
    print(f"--- 인증 분기 테스트 시작 ---")
    
    # 1. Posts API 테스트
    print(f"\n[1] Posts API 테스트")
    payload = {"title": "Auth Test Post", "status": "draft", "content": "test content"}
    try:
        resp_posts = requests.post(
            url_posts, json=payload,
            auth=HTTPBasicAuth(username, app_password),
            timeout=30,
        )
        print(f"Status: {resp_posts.status_code}")
        print(f"Response: {resp_posts.text}")
    except Exception as e:
        print(f"Posts API 예외: {e}")

    # 2. Media API 테스트
    print(f"\n[2] Media API 테스트")
    # 파일 생성
    test_file = Path("test_upload.txt")
    test_file.write_text("test content", encoding="utf-8")
    
    headers = {
        "Content-Disposition": f"attachment; filename={test_file.name}",
        "Content-Type": "text/plain"
    }
    
    try:
        with open(test_file, "rb") as f:
            resp_media = requests.post(
                url_media, data=f, headers=headers,
                auth=HTTPBasicAuth(username, app_password),
                timeout=30,
            )
        print(f"Status: {resp_media.status_code}")
        print(f"Response: {resp_media.text}")
    except Exception as e:
        print(f"Media API 예외: {e}")
    finally:
        if test_file.exists(): test_file.unlink()

if __name__ == "__main__":
    test_auth()
