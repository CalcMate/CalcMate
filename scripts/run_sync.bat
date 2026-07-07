@echo off
cd /d "%~dp0.."
REM Content Sync Engine — WordPress 기준으로 Google Sheets 상태 1회 동기화.
REM Windows 작업 스케줄러(매일 03:00)에서 이 배치를 호출하도록 등록해서 사용한다.
REM 요일에 따라 recent/full 자동 분기가 필요하면 인자 없이 run_sync_loop 대신
REM --once 로 매일 recent 를 돌리고, 주 1회 full 은 별도 트리거를 두면 된다.
.venv\Scripts\python.exe run_sync.py --once --mode recent
