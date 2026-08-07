import sys
from pathlib import Path
import requests
from requests.auth import HTTPBasicAuth
from modules.config_loader import load_config
from modules.publisher import _wp_auth

# 설정 로드
cfg = load_config('config/config.yaml')
base_url = cfg.get("WORDPRESS_URL", "").rstrip("/")
auth = HTTPBasicAuth(*_wp_auth(cfg))

# 세션 생성
session = requests.Session()
session.auth = auth

def fetch(endpoint):
    try:
        resp = session.get(f"{base_url}{endpoint}", timeout=30)
        return resp
    except Exception as e:
        return e

def run_audit():
    print("--- 권한/환경 조사 시작 ---")
    
    # 1. users/me 조회 (capabilities 포함 시도)
    print(f"\n[1] users/me 조회 (context=edit으로 capabilities 확인)")
    res_me = session.get(f"{base_url}/wp-json/wp/v2/users/me", params={"context": "edit"}, timeout=30)
    print(f"Status: {res_me.status_code}")
    print(f"Body: {res_me.text}")

    # 2. 플러그인 조회
    print(f"\n[2] 플러그인 조회")
    res_plugins = fetch("/wp-json/wp/v2/plugins")
    print(f"Status: {res_plugins.status_code if isinstance(res_plugins, requests.Response) else 'Error'}")
    print(f"Body: {res_plugins.text if isinstance(res_plugins, requests.Response) else res_plugins}")

    # 3. 테마 조회
    print(f"\n[3] 테마 조회")
    res_themes = fetch("/wp-json/wp/v2/themes")
    print(f"Status: {res_themes.status_code if isinstance(res_themes, requests.Response) else 'Error'}")
    print(f"Body: {res_themes.text if isinstance(res_themes, requests.Response) else res_themes}")

if __name__ == "__main__":
    run_audit()
