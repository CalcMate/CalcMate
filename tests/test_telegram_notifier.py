import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.telegram_notifier import send_success, send_failure, send_warning

# Mock environment variables to test missing config
def test_missing_config():
    print("Testing missing config...")
    if 'TELEGRAM_BOT_TOKEN' in os.environ: del os.environ['TELEGRAM_BOT_TOKEN']
    if 'TELEGRAM_CHAT_ID' in os.environ: del os.environ['TELEGRAM_CHAT_ID']
    
    # Should not crash
    send_success("This should not send.")
    print("Missing config test passed (no crash).")

# Simulate calls
def test_functionality():
    print("Testing functionality (requires actual ENV setup)...")
    # Assuming user has set these in their environment for real verification
    send_success("Test Success")
    send_failure("Test Failure")
    send_warning("Test Warning")
    print("Functional calls completed.")

if __name__ == "__main__":
    test_missing_config()
    test_functionality()
