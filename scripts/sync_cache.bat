@echo off
cd /d "%~dp0.."
echo 대시보드 캐시 동기화(원본→SQLite 미러)...
.venv\Scripts\python.exe -m modules.dashboard_cache
pause
