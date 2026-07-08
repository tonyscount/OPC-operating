"""测试配置 & Fixtures"""

import asyncio
import os

# 测试环境标记 — 必须在导入 app 模块前设置，关闭限流/日志等
os.environ.setdefault("TESTING", "true")

# 强制使用 127.0.0.1 (避免 Windows ProactorEventLoop 的 localhost DNS 解析问题)
# 同时也确保 app 内 settings.DATABASE_URL 使用测试库 opc_test
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://opc_user:opc_dev_password@127.0.0.1:5432/opc_test",
)

# 触发所有模型注册到 Base.metadata (必须在 create_all 之前)
import app.modules  # noqa: E402, F401

from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import create_app
from app.shared.models import Base


# 优先读环境变量 DATABASE_URL (CI 注入)，本地回退到开发默认值
# 注: 使用 127.0.0.1 而非 localhost，避免 Windows ProactorEventLoop 的 DNS 解析问题
TEST_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://opc_user:opc_dev_password@127.0.0.1:5432/opc_test",
)

# 为没有 PG 环境的场景提供标记
pytestmark = None


@pytest.fixture(scope="session")
def event_loop():
    """
    创建 session 级别的事件循环，确保整个测试会话使用同一个 loop。

    这解决了 SQLAlchemy async engine (及其 asyncpg 连接池) 与
    pytest-asyncio 之间的事件循环不匹配问题。
    所有 async fixture 和测试函数将共享此 loop。
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine(event_loop):
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
    # 重置模块级引擎 — 前一个测试的 lifespan shutdown 可能已将其 dispose
    from app.core.database import _reset_engine
    _reset_engine()

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
    import uuid
    # 注册
    resp = await client.post("/api/v1/auth/register", json={
        "tenant_name": "Auth Test",
        "tenant_slug": f"auth-test-{uuid.uuid4().hex[:8]}",
        "username": "testuser",
        "password": "testpass123456",
        "email": "test@test.com",
    })
    assert resp.status_code == 201
    data = resp.json()
    return {"Authorization": f"Bearer {data['access_token']}"}
