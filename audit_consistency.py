import requests
from requests.auth import HTTPBasicAuth
from pathlib import Path
from modules.config_loader import load_config
from modules.publisher import _wp_auth

# 설정 로드
cfg = load_config('config/config.yaml')
base_url = cfg.get("WORDPRESS_URL", "").rstrip("/")
username, app_password = _wp_auth(cfg)
auth = HTTPBasicAuth(username, app_password)

# 세션 생성 (동일 인증/세션 유지)
session = requests.Session()
session.auth = auth

def run_test():
    print(f"--- 인증 고정 조건 테스트 ---")
    print(f"URL: {base_url}")
    print(f"Auth User: {username}")
    print(f"Auth Pass Length: {len(app_password)}")
    
    def log_request(res):
        # 헤더 체크 (마스킹)
        auth_header = res.request.headers.get('Authorization', '없음')
        auth_info = f"Exists: {auth_header != '없음'}, Length: {len(auth_header)}"
        print(f"Header: {auth_info}")
        print(f"Status: {res.status_code}")
        print(f"Body: {res.text[:100]}...")

    # 1. users/me
    print(f"\n[1] Python users/me")
    res1 = session.get(f"{base_url}/wp-json/wp/v2/users/me", timeout=30)
    log_request(res1)

    # 2. posts
    print(f"\n[2] Python posts")
    payload = {"title": "Auth Test Post", "status": "draft", "content": "test content"}
    res2 = session.post(f"{base_url}/wp-json/wp/v2/posts", json=payload, timeout=30)
    log_request(res2)

if __name__ == "__main__":
    run_test()
