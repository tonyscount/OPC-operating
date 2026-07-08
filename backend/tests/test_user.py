"""用户模块测试 — 个人资料 / 密码修改 / 用户搜索"""

import pytest
from httpx import AsyncClient


@pytest.fixture
async def auth(client: AsyncClient) -> dict:
    """创建测试租户并登录"""
    import uuid
    slug = f"user-test-{uuid.uuid4().hex[:8]}"
    resp = await client.post("/api/v1/auth/register", json={
        "tenant_name": "User Test Co", "tenant_slug": slug,
        "username": "profile_owner", "password": "OwnerPass123",
        "display_name": "Owner", "email": "owner@test.com",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def two_users(client: AsyncClient) -> tuple[dict, dict]:
    """创建两个同租户用户 (用于跨用户查询测试)"""
    import uuid
    slug = f"utwo-{uuid.uuid4().hex[:8]}"
    # 用户 A (admin)
    r = await client.post("/api/v1/auth/register", json={
        "tenant_name": "TwoUser Co", "tenant_slug": slug,
        "username": "user_a", "password": "PassA12345",
        "display_name": "User A",
    })
    token_a = r.json()["access_token"]

    # 获取成员角色创建用户 B
    roles = await client.get("/api/v1/tenant/roles",
        headers={"Authorization": f"Bearer {token_a}"})
    member_id = None
    for role in roles.json():
        if role["name"] == "成员":
            member_id = role["id"]
            break

    # 用户 B
    r2 = await client.post("/api/v1/tenant/users", json={
        "username": "user_b", "password": "PassB12345",
        "display_name": "User B", "role_ids": [member_id] if member_id else [],
    }, headers={"Authorization": f"Bearer {token_a}"})
    user_b_id = r2.json()["id"]

    # 用户 B 登录
    r3 = await client.post("/api/v1/auth/login", json={
        "tenant_slug": slug, "username": "user_b", "password": "PassB12345",
    })
    token_b = r3.json()["access_token"]

    return (
        {"Authorization": f"Bearer {token_a}"},
        {"Authorization": f"Bearer {token_b}", "user_id": user_b_id},
    )


# ============================================================
# 个人资料
# ============================================================

@pytest.mark.asyncio
async def test_get_my_profile(client: AsyncClient, auth: dict):
    """获取自己的资料"""
    resp = await client.get("/api/v1/users/profile", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "profile_owner"
    assert data["display_name"] == "Owner"
    assert "roles" in data
    assert "stats" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_get_my_profile_unauthorized(client: AsyncClient):
    """未登录获取资料 → 401"""
    resp = await client.get("/api/v1/users/profile")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_other_user_profile(client: AsyncClient, two_users):
    """查看同租户其他用户的公开资料"""
    a, b = two_users
    resp = await client.get(f"/api/v1/users/profile/{b['user_id']}", headers=a)
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "user_b"
    assert data["display_name"] == "User B"


@pytest.mark.asyncio
async def test_get_nonexistent_user_profile(client: AsyncClient, auth: dict):
    """查看不存在的用户 → 404"""
    resp = await client.get("/api/v1/users/profile/00000000-0000-0000-0000-000000000000", headers=auth)
    assert resp.status_code == 404


# ============================================================
# 更新资料
# ============================================================

@pytest.mark.asyncio
async def test_update_profile(client: AsyncClient, auth: dict):
    """更新自己的昵称和邮箱"""
    resp = await client.patch("/api/v1/users/profile", headers=auth, json={
        "display_name": "New Name",
        "email": "new@test.com",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "资料已更新"
    assert data["display_name"] == "New Name"

    # 验证 GET 也更新了
    resp2 = await client.get("/api/v1/users/profile", headers=auth)
    assert resp2.json()["display_name"] == "New Name"


@pytest.mark.asyncio
async def test_update_profile_empty_body(client: AsyncClient, auth: dict):
    """空更新体 — 什么都不改"""
    resp = await client.patch("/api/v1/users/profile", headers=auth, json={})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_profile_unauthorized(client: AsyncClient):
    """未登录修改资料 → 401"""
    resp = await client.patch("/api/v1/users/profile", json={"display_name": "Hack"})
    assert resp.status_code == 401


# ============================================================
# 密码修改
# ============================================================

@pytest.mark.asyncio
async def test_change_password(client: AsyncClient, auth: dict):
    """修改密码 — 正确旧密码"""
    resp = await client.post("/api/v1/users/profile/password", headers=auth, json={
        "old_password": "OwnerPass123",
        "new_password": "NewPass45678",
    })
    assert resp.status_code == 200
    assert resp.json()["message"] == "密码已修改"


@pytest.mark.asyncio
async def test_change_password_wrong_old(client: AsyncClient, auth: dict):
    """修改密码 — 错误旧密码 → 422"""
    resp = await client.post("/api/v1/users/profile/password", headers=auth, json={
        "old_password": "WrongOldPass",
        "new_password": "NewPass45678",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_change_password_too_short(client: AsyncClient, auth: dict):
    """新密码太短 → 422"""
    resp = await client.post("/api/v1/users/profile/password", headers=auth, json={
        "old_password": "OwnerPass123",
        "new_password": "1234567",  # < 8 chars
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_change_password_unauthorized(client: AsyncClient):
    """未登录改密码 → 401"""
    resp = await client.post("/api/v1/users/profile/password", json={
        "old_password": "x", "new_password": "NewPass12345",
    })
    assert resp.status_code == 401


# ============================================================
# 用户搜索
# ============================================================

@pytest.mark.asyncio
async def test_search_users(client: AsyncClient, auth: dict):
    """搜索用户 — 按用户名"""
    resp = await client.get("/api/v1/users/search?q=profile_owner", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    usernames = [u["username"] for u in data["items"]]
    assert "profile_owner" in usernames


@pytest.mark.asyncio
async def test_search_users_no_results(client: AsyncClient, auth: dict):
    """搜索无结果"""
    resp = await client.get("/api/v1/users/search?q=xyznonexistent999", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_search_users_pagination(client: AsyncClient, two_users):
    """搜索分页"""
    a, _ = two_users
    resp = await client.get("/api/v1/users/search?q=user&page=1&page_size=1", headers=a)
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 1
    assert len(data["items"]) <= 1


@pytest.mark.asyncio
async def test_search_users_empty_query(client: AsyncClient, auth: dict):
    """空搜索词 → 422"""
    resp = await client.get("/api/v1/users/search?q=", headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_search_users_unauthorized(client: AsyncClient):
    """未登录搜索 → 401"""
    resp = await client.get("/api/v1/users/search?q=test")
    assert resp.status_code == 401
