@echo off
setlocal
title Bastion Forge Stream Hub Auth Gateway
cd /d "%~dp0"
call .venv\Scripts\activate
python run_gateway.py
pause
