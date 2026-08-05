import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.telegram_notifier import send_success, send_failure, send_warning

_EMPTY_CFG = {}
_MOCK_CFG = {"TELEGRAM_BOT_TOKEN": "fake_token", "TELEGRAM_CHAT_ID": "fake_chat"}

def test_missing_config():
    print("Testing missing config...")
    # Should not crash — missing token/chat_id → graceful skip
    send_success(_EMPTY_CFG, "This should not send.")
    print("Missing config test passed (no crash).")

def test_functionality():
    print("Testing functionality (no real network call — token is fake)...")
    # Fake token → Telegram API will reject, but the call itself must not raise
    send_success(_MOCK_CFG, "Test Success")
    send_failure(_MOCK_CFG, "Test Failure")
    send_warning(_MOCK_CFG, "Test Warning")
    print("Functional calls completed.")

if __name__ == "__main__":
    test_missing_config()
    test_functionality()
