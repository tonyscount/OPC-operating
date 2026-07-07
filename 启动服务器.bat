@echo off
chcp 65001 >nul
title OPC Platform Server

cd /d "%~dp0backend"

:: 杀端口
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTEN"') do taskkill /F /PID %%a >nul 2>&1

:: 启动
set PYTHONPATH=%~dp0backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

pause
