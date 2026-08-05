"""
scripts/rms_annual_check.py — 연 1회 정기 점검 Orchestration
"""
import subprocess
import sys
import os
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent.parent

def main():
    print("--- [RMS Annual Check] Started ---")
    
    # 1. Run rms_check.py
    print("Running rms_check.py...")
    subprocess.run([sys.executable, "-m", "scripts.rms_check"], check=True)
    
    # 2. Check for drafts
    draft_file = ROOT / "docs" / "legal_basis.draft.yaml"
    if not draft_file.exists():
        print("No changes (no draft found). Sending notification.")
        from modules.config_loader import load_config
        from modules.telegram_notifier import send_message
        cfg = load_config(str(ROOT / "config" / "config.yaml"))
        send_message(cfg, "정기 점검 완료, 변경사항 없음")
        return

    # 3. If drafts found, run regression
    print("Changes detected (draft found). Running regression...")
    # As per requirements, calling regression. 
    # Since I cannot modify it, and it sends its own notifications, 
    # I'll just run it and let it handle the reporting.
    subprocess.run([sys.executable, "-m", "scripts.rms_regression"], check=True)
    
    print("--- [RMS Annual Check] Completed ---")

if __name__ == "__main__":
    main()
