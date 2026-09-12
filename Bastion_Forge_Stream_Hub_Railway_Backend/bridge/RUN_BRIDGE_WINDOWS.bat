@echo off
title Bastion Forge Kick Bridge
cd /d "%~dp0"
call .venv\Scripts\activate
python run_bridge.py
pause
