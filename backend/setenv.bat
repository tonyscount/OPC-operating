@echo off
REM OPC Platform — Windows 快速启动
echo === OPC 开发环境设置 ===

REM 1. 复制环境变量
if not exist .env copy .env.example .env
echo [OK] .env 已就绪 (请编辑填入真实密钥)

REM 2. 安装依赖 (如网络有问题，先开代理)
pip install -r requirements.txt
echo [OK] 依赖安装完成

REM 3. 数据库迁移
alembic upgrade head
echo [OK] 数据库迁移完成

REM 4. Seed 数据
python -m alembic.seed
echo [OK] 测试数据已创建 (admin/admin123456)

REM 5. 启动
echo === 启动 API 服务器 ===
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
