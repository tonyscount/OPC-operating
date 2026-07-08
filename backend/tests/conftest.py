"""测试配置 & Fixtures"""

import asyncio
import os

# 测试环境标记 — 必须在导入 app 模块前设置，关闭限流/日志等
os.environ.setdefault("TESTING", "true")

from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import create_app
from app.shared.models import Base


# 优先读环境变量 DATABASE_URL (CI 注入)，本地回退到开发默认值
TEST_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://opc_user:opc_dev_password@localhost:5432/opc_test",
)

# 为没有 PG 环境的场景提供标记
pytestmark = None


@pytest_asyncio.fixture(scope="session")
async def engine():
    """创建测试引擎"""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    # 清理
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db(engine) -> AsyncGenerator[AsyncSession, None]:
    """每个测试独立的数据库会话 (回滚)"""
    async with engine.connect() as conn:
        async with conn.begin() as transaction:
            session = AsyncSession(bind=conn, expire_on_commit=False)
            yield session
            await transaction.rollback()
        await conn.close()


@pytest_asyncio.fixture
async def client(db) -> AsyncGenerator[AsyncClient, None]:
    """FastAPI 测试客户端"""
    app = create_app()
    app.dependency_overrides = {}  # 可在此覆盖依赖

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def demo_tenant(db) -> str:
    """创建演示租户，返回 tenant_id"""
    from app.modules.tenant.service import create_tenant
    tenant = await create_tenant(db, name="Test Corp", slug="test-corp")
    return str(tenant.id)


@pytest_asyncio.fixture
async def auth_headers(client, db) -> dict:
    """获取认证 Header (自动创建租户、用户并登录)"""
    # 注册
    resp = await client.post("/api/v1/auth/register", json={
        "tenant_name": "Auth Test",
        "tenant_slug": "auth-test",
        "username": "testuser",
        "password": "testpass123456",
        "email": "test@test.com",
    })
    assert resp.status_code == 201
    data = resp.json()
    return {"Authorization": f"Bearer {data['access_token']}"}
