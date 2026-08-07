import requests
from requests.auth import HTTPBasicAuth
from pathlib import Path
from modules.config_loader import load_config
from modules.publisher import _wp_auth

# 설정 로드
cfg = load_config('config/config.yaml')
base_url = cfg.get("WORDPRESS_URL", "").rstrip("/")
auth = HTTPBasicAuth(*_wp_auth(cfg))

# 세션 생성 (동일 인증/세션 유지)
session = requests.Session()
session.auth = auth

def run_test():
    print("--- 3개 엔드포인트 연속 테스트 시작 ---")
    
    # 1. users/me
    url1 = f"{base_url}/wp-json/wp/v2/users/me"
    res1 = session.get(url1, timeout=30)
    print(f"\n[1] users/me")
    print(f"URL: {url1}")
    print(f"Status: {res1.status_code}")
    print(f"Body: {res1.text}")

    # 2. posts
    url2 = f"{base_url}/wp-json/wp/v2/posts"
    payload2 = {"title": "Test Post", "status": "draft", "content": "Test"}
    res2 = session.post(url2, json=payload2, timeout=30)
    print(f"\n[2] posts")
    print(f"URL: {url2}")
    print(f"Status: {res2.status_code}")
    print(f"Body: {res2.text}")

    # 3. media
    url3 = f"{base_url}/wp-json/wp/v2/media"
    test_file = Path("test_upload.txt")
    test_file.write_text("test content", encoding="utf-8")
    headers = {"Content-Disposition": f"attachment; filename={test_file.name}", "Content-Type": "text/plain"}
    
    try:
        with open(test_file, "rb") as f:
            res3 = session.post(url3, data=f, headers=headers, timeout=60)
        print(f"\n[3] media")
        print(f"URL: {url3}")
        print(f"Status: {res3.status_code}")
        print(f"Body: {res3.text}")
    finally:
        if test_file.exists(): test_file.unlink()

if __name__ == "__main__":
    run_test()
