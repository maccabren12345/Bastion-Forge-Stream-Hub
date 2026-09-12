@echo off
title Bastion Forge Kick Bridge Setup
cd /d "%~dp0"
python -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist .env copy .env.example .env >nul
echo.
echo Setup complete.
echo Edit bridge\.env and change BASTION_BRIDGE_KEY before running the bridge.
pause
