@echo off
REM ============================================================
REM  run_sync.bat — Content Sync(WP→Sheets) 상시 실행 런처
REM  (대시보드 브라우저 접속 없이도 매일 동기화가 돌도록 독립 프로세스로 구동)
REM
REM  실행: python run_sync.py  → run_sync_loop
REM  ※ 동기화 '시각'(기본 03:00, CONTENT_SYNC.run_at)은 루프 내부에서 판정한다.
REM    따라서 작업 스케줄러 트리거는 "시간(03:00)"이 아니라 "로그온 시 상시 실행"으로 건다.
REM    (03:00 시간 트리거로 걸지 말 것 — 이중 스케줄이 됨)
REM
REM  중복 실행 방지: run_sync_loop 은 last_run_date(영속 마커) + content_sync.lock 으로
REM  '하루 1회'만 실행한다. 대시보드 내장 content-sync 스레드와 병행해도 겹치지 않는다.
REM  재부팅 등으로 03:00 을 놓쳤으면 시작 시 catch-up 으로 밀린 오늘분 1회 즉시 처리.
REM ============================================================
chcp 65001 >nul
cd /d "%~dp0"

if not exist "data\logs" mkdir "data\logs"

:loop
echo [%date% %time%] content-sync starting >> "data\logs\sync_stdout.log"
".venv\Scripts\python.exe" run_sync.py >> "data\logs\sync_stdout.log" 2>&1
echo [%date% %time%] content-sync exited (code %errorlevel%) - restarting in 30s >> "data\logs\sync_stdout.log"
timeout /t 30 /nobreak >nul
goto loop
