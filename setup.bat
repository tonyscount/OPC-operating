@echo off
chcp 65001 >nul
title OPC Platform — 本地开发环境初始化

echo ============================================================
echo   OPC Platform — 本地开发环境初始化
echo ============================================================
echo.

REM ====== Step 0: 检查 PostgreSQL ======
echo [0/4] 检查 PostgreSQL...
where psql >nul 2>&1
if %errorlevel% neq 0 (
    echo   [错误] PostgreSQL 未安装或不在 PATH 中
    echo.
    echo   请先安装 PostgreSQL 15+:
    echo     - 下载: https://www.enterprisedb.com/downloads/postgres-postgresql-downloads
    echo     - 或 winget: winget install PostgreSQL.PostgreSQL.15
    echo     - 安装时记住 postgres 用户的密码
    echo     - 安装后重启终端再运行本脚本
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('psql --version 2^>^&1') do echo   PostgreSQL %%v [OK]
echo.

REM ====== Step 1: 创建数据库和用户 ======
echo [1/4] 创建数据库和用户...
set PGPASSWORD=postgres
psql -U postgres -c "CREATE USER opc_user WITH PASSWORD 'opc_dev_password';" 2>nul
psql -U postgres -c "CREATE DATABASE opc_platform OWNER opc_user;" 2>nul
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE opc_platform TO opc_user;" 2>nul
echo   [OK] 数据库和用户已创建
echo.

REM ====== Step 2: 安装 pgvector 扩展 ======
echo [2/4] 安装 pgvector 扩展...
psql -U postgres -d opc_platform -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>nul
psql -U postgres -d opc_platform -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";" 2>nul
psql -U postgres -d opc_platform -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;" 2>nul
echo   [OK] 扩展已安装
echo.

REM ====== Step 3: 安装 Python 依赖 ======
echo [3/4] 安装 Python 依赖...
call python -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r backend\requirements.txt --quiet 2>&1
echo   [OK] 依赖已安装
echo.

REM ====== Step 4: 数据库迁移 + Seed ======
echo [4/4] 数据库迁移...
cd backend
copy .env.local .env /Y >nul 2>&1
call python -m alembic upgrade head
echo   [OK] 迁移完成
echo.
echo   创建演示数据...
call python -m alembic.seed
echo   [OK] 演示数据已创建
cd ..
echo.

echo ============================================================
echo   初始化完成!
echo.
echo   启动 API 服务器:
echo     cd backend
echo     uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
echo.
echo   然后打开: http://localhost:8000/api/docs
echo.
echo   演示账号: admin / admin123456 (tenant=demo)
echo ============================================================
pause
