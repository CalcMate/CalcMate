import sys
import json
import os
from pathlib import Path

# 프로젝트 루트를 경로에 추가
sys.path.append(os.getcwd())

# 모듈 로드
from modules.config_loader import load_config
from modules.calculator_pipeline import run_calculator_once

# 설정 로드
cfg = load_config()

# 테스트 대상: 주휴수당
# slug: weekly-holiday-allowance
# cid를 확인해야 함
# 예시: C:\Users\연수\Desktop\블로그자동_v12\modules\calculator_seed.py 참고
# CID는 보통 계산기 시드에서 관리됨.

# 일단 cid를 찾기 위해 콜렉터를 써보거나, 이미 알고 있는 cid 확인 필요.
# 문서나 기존 코드에 따르면 cid는 calculator_id임.

# 콜렉터로 목록 확인
from modules.collector.factory import get_collector
collectors = get_collector("calculator")
items = collectors.collect(cfg, site=None)

# 주휴수당 찾기 (title 기반)
target_calc = next((item for item in items if '주휴수당' in item.get("title", "")), None)
if not target_calc:
    print(f"Error: 주휴수당 계산기를 찾을 수 없습니다. Items: {items[0] if items else 'None'}")
    sys.exit(1)

target_cid = str(target_calc.get("calculator_id"))
print(f"Target CID: {target_cid}")

# E2E 검증 실행
# intent=eligibility
# allow_duplicate=True로 매번 새 Draft 생성
result = run_calculator_once(
    cfg, 
    only_cid=target_cid, 
    intent="eligibility", 
    allow_duplicate=True,
    skip_quality=False # 실제 파이프라인 검증
)

print(f"Result: {result}")
