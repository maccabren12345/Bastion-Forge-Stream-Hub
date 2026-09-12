@echo off
setlocal
cd /d "%~dp0"
python -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist ".env" copy ".env.example" ".env" >nul
if not exist "manifest-private-beta.json" copy "manifest-private-beta.example.json" "manifest-private-beta.json" >nul
echo.
echo Beta backend installed. Edit .env before exposing it through HTTPS.
pause
