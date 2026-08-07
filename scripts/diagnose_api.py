import yaml
import sys
import os
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.utils.health_monitor import _check_openai, _check_claude, _check_gemini

# secrets.yaml 키 존재 및 길이 확인
def check_secrets():
    path = Path("config/secrets.yaml")
    if not path.exists():
        print("secrets.yaml not found")
        return
    
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    keys = ["OPENAI_API_KEY", "CLAUDE_API_KEY", "GEMINI_API_KEY"]
    for k in keys:
        val = data.get(k)
        if val:
            print(f"{k}: 설정됨 (길이: {len(str(val))})")
        else:
            print(f"{k}: 비어있음")

# 실제 헬스체크 실행 및 결과 확인 (cfg 모의 객체 사용)
def run_health_checks():
    # 간단한 cfg 모의 객체 구성
    path = Path("config/secrets.yaml")
    with open(path, 'r', encoding='utf-8') as f:
        secrets = yaml.safe_load(f)
    
    # config.yaml도 필요함
    path_config = Path("config/config.yaml")
    with open(path_config, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    cfg = {**config, **secrets}

    print("\n--- 헬스체크 원본 에러 메시지 ---")
    print("OpenAI:", _check_openai(cfg))
    print("Claude:", _check_claude(cfg))
    print("Gemini:", _check_gemini(cfg))

if __name__ == "__main__":
    check_secrets()
    run_health_checks()
