@echo off
REM 로그온 시 자동 기동용 대시보드 실행 배치 (작업 스케줄러 / 시작프로그램 등록용).
REM --server.headless true : 브라우저 자동 오픈/이메일 프롬프트 없이 백그라운드 상주.
REM 대시보드가 떠 있으면 content_sync 스레드도 함께 기동되어 매일 03:00(+시작 시 catch-up) 동기화된다.
cd /d "%~dp0.."
.venv\Scripts\streamlit.exe run dashboard.py --server.headless true
