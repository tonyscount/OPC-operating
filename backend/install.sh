#!/bin/bash
# OPC Platform — 一键安装脚本 (适用于 Windows Git Bash / Linux)
set -e

echo "=== OPC Platform 依赖安装 ==="

# 方法 1: PyPI 直装 (需稳定网络)
pip install \
  "fastapi>=0.115.0" "uvicorn[standard]>=0.30.0" "starlette>=0.41.0" "python-multipart>=0.0.9" \
  "sqlalchemy[asyncio]>=2.0.30" "asyncpg>=0.30.0" "alembic>=1.14.0" "pgvector>=0.3.0" \
  "pydantic>=2.10.0" "pydantic-settings>=2.7.0" "pyyaml>=6.0" \
  "python-jose[cryptography]>=3.3.0" "bcrypt>=4.2.0" \
  "celery[redis]>=5.4.0" "redis>=5.2.0" "slowapi>=0.1.9" \
  "openai>=1.50.0" "langgraph>=0.2.0" "langchain>=0.3.0" "langchain-openai>=0.2.0" "tiktoken>=0.8.0" \
  "pypdf2>=3.0.0" "python-docx>=1.1.0" "markdown>=3.5" \
  "httpx>=0.28.0" "python-dateutil>=2.9.0" "json-repair>=0.30.0" "headroom-ai>=0.25.0" \
  "loguru>=0.7.0" "pytest>=8.0.0" "pytest-asyncio>=0.25.0" "factory-boy>=3.3.0"

echo "=== 依赖安装完成 ==="

# 方法 2 (备选): 使用 Headroom 自带的 wheel
# pip install ../headroom-main/target/wheels/headroom_ai-0.25.0-cp310-abi3-win_amd64.whl
