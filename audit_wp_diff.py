import sys
from pathlib import Path
import requests
from requests.auth import HTTPBasicAuth
from modules.config_loader import load_config
from modules.publisher import _wp_auth

# 프로젝트 루트 설정 및 Config 로드
ROOT = Path(__file__).resolve().parent
cfg = load_config(str(ROOT / "config" / "config.yaml"))
base_url = cfg.get("WORDPRESS_URL", "").rstrip("/")
auth = HTTPBasicAuth(*_wp_auth(cfg))

def fetch(endpoint):
    try:
        resp = requests.get(f"{base_url}{endpoint}", auth=auth, timeout=30)
        return resp
    except Exception as e:
        return e

def run_audit():
    print(f"--- 환경 설정 검증 ---")
    print(f"URL: {base_url}")
    print(f"사용자: {cfg.get('WORDPRESS_USERNAME')}")
    
    # 1. /wp-json 조회
    print(f"\n--- [1] /wp-json 조회 ---")
    res_json = fetch("/wp-json")
    if isinstance(res_json, requests.Response):
        print(f"Status: {res_json.status_code}")
        data = res_json.json()
        print(f"Name: {data.get('name')}")
        print(f"Version: {data.get('version')}")
        print(f"X-Powered-By: {res_json.headers.get('X-Powered-By')}")
    else:
        print(f"예외: {res_json}")

    # 2. /wp-json/wp/v2/users/me 조회
    print(f"\n--- [2] /wp-json/wp/v2/users/me 조회 ---")
    res_me = fetch("/wp-json/wp/v2/users/me")
    if isinstance(res_me, requests.Response):
        print(f"Status: {res_me.status_code}")
        data = res_me.json()
        print(f"ID: {data.get('id')}")
        print(f"Roles: {data.get('roles')}")
        print(f"Response Body: {res_me.text}")
    else:
        print(f"예외: {res_me}")

if __name__ == "__main__":
    run_audit()
