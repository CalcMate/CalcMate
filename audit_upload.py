import sys
from pathlib import Path
from requests.auth import HTTPBasicAuth
import requests
import re
import mimetypes

# 1. 시뮬레이션 설정 (main.py 호출 흐름 모방)
from modules.config_loader import load_config
from modules.publisher import _wp_auth
cfg = load_config('config/config.yaml')
fpath = Path('data/outputs/20260803222627_thumb.webp')
url = cfg.get("WORDPRESS_URL", "").rstrip("/") + "/wp-json/wp/v2/media"

# 2. 인증 객체 확인
auth = HTTPBasicAuth(*_wp_auth(cfg))
print(f"--- 1. upload_media 진입 ---")
print(f"Auth 객체 존재: {auth is not None}")
print(f"URL: {url}")
print(f"파일명: {fpath.name}")

# 3. 헤더 구성
mime_type, _ = mimetypes.guess_type(fpath)
if not mime_type: mime_type = "image/webp"
headers = {
    "Content-Disposition": f"attachment; filename={fpath.name}",
    "Content-Type": mime_type
}

# 4. requests.post 호출 직전 확인
print(f"\n--- 2. requests.post 직전 ---")
print(f"헤더 키 목록: {list(headers.keys())}")
print(f"Authorization 헤더 추정(Basic): {auth.username is not None and auth.password is not None}")
print(f"Content-Type: {headers.get('Content-Type')}")
print(f"Content-Disposition: {headers.get('Content-Disposition')}")

# 5. 실제 요청 및 응답 캡처
try:
    with open(fpath, "rb") as f:
        resp = requests.post(
            url, data=f, headers=headers,
            auth=auth,
            timeout=60,
        )
    print(f"\n--- 3. 401/응답 상세 ---")
    print(f"Status Code: {resp.status_code}")
    print(f"Response Body: {resp.text}")
    print(f"WWW-Authenticate 헤더: {resp.headers.get('WWW-Authenticate', '없음')}")
except Exception as e:
    print(f"요청 예외: {e}")
