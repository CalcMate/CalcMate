@echo off
:: 정기 점검 자동 실행 배치파일
cd /d %~dp0

:: 가상환경 활성화 (프로젝트 구조에 맞게 설정)
call .venv\Scripts\activate

:: 정기 점검 오케스트레이터 실행
python -m scripts.rms_annual_check
