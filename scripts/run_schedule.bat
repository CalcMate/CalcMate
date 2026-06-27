@echo off
cd /d "%~dp0.."
echo 스케줄 모드 시작 (RUN_INTERVAL_HOURS 간격 반복)...
.venv\Scripts\python.exe main.py --schedule
pause
