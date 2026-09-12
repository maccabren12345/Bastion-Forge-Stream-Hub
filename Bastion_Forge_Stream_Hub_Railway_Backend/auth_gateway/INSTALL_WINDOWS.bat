@echo off
setlocal
title Bastion Forge Auth Gateway Setup
cd /d "%~dp0"

python -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt

if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo.
  echo Created .env
  echo Edit it and enter the Bastion Forge provider app credentials.
)

echo.
echo Auth Gateway setup complete.
pause
