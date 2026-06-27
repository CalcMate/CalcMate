@echo off
cd /d "%~dp0.."
echo Starting Dashboard...
.venv\Scripts\streamlit.exe run dashboard.py
pause
