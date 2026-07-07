@echo off
chcp 65001 >nul
title OPC Platform Server

cd backend
echo ============================================================
echo   OPC Platform API Server
echo   http://localhost:8000/api/docs
echo ============================================================

call python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
