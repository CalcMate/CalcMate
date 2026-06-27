@echo off
cd /d "%~dp0.."
echo 전략회의실 즉시 실행...
.venv\Scripts\python.exe main.py --strategy-room
pause
