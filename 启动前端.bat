@echo off
title OPC Frontend
cd /d "%~dp0web"
npx vite --host 0.0.0.0 --port 3000
pause
