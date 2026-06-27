@echo off
cd /d "%~dp0.."
echo 슬롯 발행 스케줄러 시작 (오늘 일정대로 시각별 1건 발행)...
.venv\Scripts\python.exe main.py --scheduler
pause
