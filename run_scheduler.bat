@echo off
REM ============================================================
REM  run_scheduler.bat — 예약 발행 스케줄러 상시 실행 런처
REM  (브라우저/대시보드와 무관하게 항상 발행되도록 독립 프로세스로 구동)
REM
REM  실행: python main.py --scheduler  → run_scheduler_loop
REM  자동 재시작: 프로세스가 죽거나 정상 종료해도 10초 후 재기동(무한 루프).
REM  작업 스케줄러에 "로그온 시 시작"으로 등록해 사용한다(docs/OPS_TASK_SCHEDULER_GUIDE.md).
REM
REM  중복 발행 방지: modules/scheduler 의 파일 락(_acquire_lock)이
REM  대시보드 내장 스레드와 병행 실행돼도 동시 발행을 막는다.
REM ============================================================
chcp 65001 >nul
cd /d "%~dp0"

if not exist "data\logs" mkdir "data\logs"

:loop
echo [%date% %time%] publish-scheduler starting >> "data\logs\scheduler_stdout.log"
".venv\Scripts\python.exe" main.py --scheduler >> "data\logs\scheduler_stdout.log" 2>&1
echo [%date% %time%] publish-scheduler exited (code %errorlevel%) - restarting in 10s >> "data\logs\scheduler_stdout.log"
timeout /t 10 /nobreak >nul
goto loop
