import sys
sys.path.append('.')
from modules.config_loader import load_config
import os

cfg = load_config('config/config.yaml')
token_env = os.getenv('TELEGRAM_BOT_TOKEN')
chat_id_env = os.getenv('TELEGRAM_CHAT_ID')

token_cfg = cfg.get('TELEGRAM_BOT_TOKEN')
chat_id_cfg = cfg.get('TELEGRAM_CHAT_ID')

print(f"--- 환경변수(os.getenv) 결과 ---")
print(f"TOKEN: {token_env}")
print(f"CHAT_ID: {chat_id_env}")

print(f"\n--- cfg (merged config/secrets) 결과 ---")
print(f"TOKEN: {token_cfg}")
print(f"CHAT_ID: {chat_id_cfg}")
