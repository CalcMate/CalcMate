@echo off
cd /d "%~dp0.."
echo Starting SalaryMate OS (SaaS UI)...
.venv\Scripts\streamlit.exe run dashboard_ui_refactor.py
pause
