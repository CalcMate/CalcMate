@echo off
cd /d "%~dp0.."
echo [dry-run] 설정 검증 및 헬스체크 실행...
.venv\Scripts\python.exe main.py --dry-run
pause
