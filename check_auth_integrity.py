import yaml
import requests
from requests.auth import HTTPBasicAuth

# 1. secrets.yaml 직접 읽기
with open('config/secrets.yaml', 'r', encoding='utf-8') as f:
    secrets = yaml.safe_load(f)

wp = secrets.get('wordpress', {})
username = wp.get('username')
password = wp.get('app_password')

print("--- 1. secrets.yaml 값 ---")
print(f"Username (repr): {repr(username)}")
print(f"Is username 'geminia'?: {username == 'geminia'}")

# 2. 분석 근거 확인 (착오 여부)
print("\n--- 2. '연수' 근거 분석 ---")
print("이전 분석에서 시스템 환경 정보(C:\\Users\\연수\\...)를 사용자명으로 혼동했을 가능성이 높습니다.")

# 3. 실제 요청 시점의 auth 값 확인
print("\n--- 3. 실제 요청 시점 auth 값 확인 ---")
auth = HTTPBasicAuth(username, password)
print(f"Auth Username: {repr(auth.username)}")
print(f"Auth Password: {repr(auth.password)}")
