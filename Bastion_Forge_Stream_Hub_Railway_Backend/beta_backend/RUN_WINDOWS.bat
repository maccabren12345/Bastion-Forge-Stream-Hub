@echo off
setlocal
cd /d "%~dp0"
call .venv\Scripts\activate
python run_backend.py
pause
