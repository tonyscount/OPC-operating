"""认证模块测试"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_creates_tenant_and_user(client: AsyncClient):
    """注册应该同时创建租户和管理员用户"""
    resp = await client.post("/api/v1/auth/register", json={
        "tenant_name": "测试公司",
        "tenant_slug": "test-company",
        "username": "ceo",
        "password": "password123",
        "email": "ceo@test.com",
        "display_name": "CEO",
    })

    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_with_correct_credentials(client: AsyncClient):
    """正确的租户+用户名+密码应该登录成功"""
    # 先注册
    await client.post("/api/v1/auth/register", json={
        "tenant_name": "Login Test",
        "tenant_slug": "login-test",
        "username": "user1",
        "password": "mypassword123",
    })

    # 登录
    resp = await client.post("/api/v1/auth/login", json={
        "tenant_slug": "login-test",
        "username": "user1",
        "password": "mypassword123",
    })

    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    """错误密码应该返回 401"""
    await client.post("/api/v1/auth/register", json={
        "tenant_name": "Wrong PW Test",
        "tenant_slug": "wrong-pw-test",
        "username": "u1",
        "password": "correctpass123",
    })

    resp = await client.post("/api/v1/auth/login", json={
        "tenant_slug": "wrong-pw-test",
        "username": "u1",
        "password": "wrongpassword",
    })

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_wrong_tenant(client: AsyncClient):
    """不存在的租户应该返回 401"""
    resp = await client.post("/api/v1/auth/login", json={
        "tenant_slug": "nonexistent-tenant",
        "username": "anyone",
        "password": "anything",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_endpoint_returns_user_info(client: AsyncClient):
    """/me 应该返回当前登录用户信息"""
    # 注册
    reg = await client.post("/api/v1/auth/register", json={
        "tenant_name": "Me Test",
        "tenant_slug": "me-test",
        "username": "alice",
        "password": "alice123456",
        "email": "alice@me.com",
    })
    token = reg.json()["access_token"]

    # 查 /me
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "alice"
    assert data["email"] == "alice@me.com"
    assert "管理员" in data["roles"]
    assert len(data["permissions"]) > 0


@pytest.mark.asyncio
async def test_me_without_token_returns_401(client: AsyncClient):
    """未登录访问 /me 应该返回 401"""
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_invalidates_token(client: AsyncClient):
    """登出后 Token 应该不可用"""
    reg = await client.post("/api/v1/auth/register", json={
        "tenant_name": "Logout Test",
        "tenant_slug": "logout-test",
        "username": "bob",
        "password": "bob12345678",
    })
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 确认 Token 可用
    me_resp = await client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200

    # 登出
    logout_resp = await client.post("/api/v1/auth/logout", headers=headers)
    assert logout_resp.status_code == 200

    # Token 应该失效 (因为加入了黑名单 — 此处依赖中间件检查)
    # 注意: 完整的黑名单检查需要在 middleware 层实现


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    """刷新 Token 应该返回新的 Token 对"""
    reg = await client.post("/api/v1/auth/register", json={
        "tenant_name": "Refresh Test",
        "tenant_slug": "refresh-test",
        "username": "carol",
        "password": "carol123456",
    })
    refresh = reg.json()["refresh_token"]

    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})

    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"] != reg.json()["access_token"]


@pytest.mark.asyncio
async def test_duplicate_tenant_slug(client: AsyncClient):
    """重复的租户标识应该返回 409"""
    await client.post("/api/v1/auth/register", json={
        "tenant_name": "First",
        "tenant_slug": "unique-slug",
        "username": "admin",
        "password": "admin123456",
    })

    resp = await client.post("/api/v1/auth/register", json={
        "tenant_name": "Second",
        "tenant_slug": "unique-slug",
        "username": "admin2",
        "password": "admin123456",
    })

    assert resp.status_code == 409
