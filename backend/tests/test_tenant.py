"""多租户模块测试"""

import pytest
from httpx import AsyncClient


@pytest.fixture
async def admin_token(client: AsyncClient) -> str:
    """创建租户并返回管理员 Token"""
    import uuid
    resp = await client.post("/api/v1/auth/register", json={
        "tenant_name": "Tenant Test Corp",
        "tenant_slug": f"tenant-test-corp-{uuid.uuid4().hex[:8]}",
        "username": "admin",
        "password": "admin123456",
    })
    return resp.json()["access_token"]


@pytest.fixture
def auth(client: AsyncClient, admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.mark.asyncio
async def test_get_tenant_info(client: AsyncClient, auth: dict):
    """获取当前租户信息"""
    resp = await client.get("/api/v1/tenant/info", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Tenant Test Corp"
    assert data["slug"].startswith("tenant-test-corp")
    assert data["plan"] == "free"


@pytest.mark.asyncio
async def test_create_org(client: AsyncClient, auth: dict):
    """创建部门"""
    resp = await client.post("/api/v1/tenant/orgs", headers=auth, json={
        "name": "技术部",
        "code": "tech",
        "sort_order": 1,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "技术部"
    assert data["code"] == "tech"


@pytest.mark.asyncio
async def test_get_org_tree(client: AsyncClient, auth: dict):
    """获取组织树"""
    # 创建两级组织
    r1 = await client.post("/api/v1/tenant/orgs", headers=auth, json={"name": "总公司", "code": "root"})
    parent_id = r1.json()["id"]
    await client.post("/api/v1/tenant/orgs", headers=auth, json={
        "name": "产品部", "code": "product", "parent_id": parent_id,
    })
    await client.post("/api/v1/tenant/orgs", headers=auth, json={
        "name": "研发部", "code": "dev", "parent_id": parent_id,
    })

    resp = await client.get("/api/v1/tenant/orgs", headers=auth)
    assert resp.status_code == 200
    tree = resp.json()
    assert len(tree) == 1  # 一个根节点
    assert tree[0]["name"] == "总公司"
    assert len(tree[0]["children"]) == 2


@pytest.mark.asyncio
async def test_cannot_delete_org_with_children(client: AsyncClient, auth: dict):
    """有子组织的部门不可删除"""
    r1 = await client.post("/api/v1/tenant/orgs", headers=auth, json={"name": "父部门"})
    parent_id = r1.json()["id"]
    await client.post("/api/v1/tenant/orgs", headers=auth, json={
        "name": "子部门", "parent_id": parent_id,
    })

    resp = await client.delete(f"/api/v1/tenant/orgs/{parent_id}", headers=auth)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_user(client: AsyncClient, auth: dict):
    """创建用户并分配角色"""
    # 先获取角色
    roles_resp = await client.get("/api/v1/tenant/roles", headers=auth)
    member_role_id = None
    for r in roles_resp.json():
        if r["name"] == "成员":
            member_role_id = r["id"]
            break
    assert member_role_id is not None

    resp = await client.post("/api/v1/tenant/users", headers=auth, json={
        "username": "newuser",
        "password": "newpass123456",
        "email": "new@test.com",
        "display_name": "新用户",
        "role_ids": [member_role_id],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "newuser"
    assert len(data["roles"]) == 1
    assert data["roles"][0]["name"] == "成员"


@pytest.mark.asyncio
async def test_list_users(client: AsyncClient, auth: dict):
    """用户列表分页"""
    resp = await client.get("/api/v1/tenant/users", headers=auth, params={"page": 1, "page_size": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1  # 至少有一个 admin 用户


@pytest.mark.asyncio
async def test_create_role(client: AsyncClient, auth: dict):
    """创建自定义角色"""
    resp = await client.post("/api/v1/tenant/roles", headers=auth, json={
        "name": "内容审核员",
        "description": "负责审核社交内容",
        "permissions": ["social:read", "social:write"],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "内容审核员"
    assert "social:read" in data["permissions"]


@pytest.mark.asyncio
async def test_cannot_delete_system_role(client: AsyncClient, auth: dict):
    """系统内置角色不可删除"""
    roles_resp = await client.get("/api/v1/tenant/roles", headers=auth)
    admin_role_id = None
    for r in roles_resp.json():
        if r["name"] == "管理员":
            admin_role_id = r["id"]
            break

    resp = await client.delete(f"/api/v1/tenant/roles/{admin_role_id}", headers=auth)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_duplicate_username_in_same_tenant(client: AsyncClient, auth: dict):
    """同租户下用户名不能重复"""
    await client.post("/api/v1/tenant/users", headers=auth, json={
        "username": "duplicated",
        "password": "pass12345678",
    })
    resp = await client.post("/api/v1/tenant/users", headers=auth, json={
        "username": "duplicated",
        "password": "anotherpass123",
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_tenant_isolation_users_cannot_see_other_tenant(client: AsyncClient):
    """租户 A 的用户不能看到租户 B 的用户"""
    # 注册租户 A
    r1 = await client.post("/api/v1/auth/register", json={
        "tenant_name": "Tenant A", "tenant_slug": "tenant-a",
        "username": "user_a", "password": "pass123456",
    })
    token_a = r1.json()["access_token"]

    # 注册租户 B
    r2 = await client.post("/api/v1/auth/register", json={
        "tenant_name": "Tenant B", "tenant_slug": "tenant-b",
        "username": "user_b", "password": "pass123456",
    })
    token_b = r2.json()["access_token"]

    # 租户 A 查用户列表，应该只看到自己的用户
    resp = await client.get("/api/v1/tenant/users", headers={"Authorization": f"Bearer {token_a}"})
    data = resp.json()

    usernames = [u["username"] for u in data["items"]]
    assert "user_a" in usernames
    assert "user_b" not in usernames  # 租户隔离生效


@pytest.mark.asyncio
async def test_permissions_endpoint(client: AsyncClient, auth: dict):
    """获取可用权限列表"""
    resp = await client.get("/api/v1/tenant/permissions", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert "permissions" in data
    assert "knowledge:*" in data["permissions"]
    assert "social:write" in data["permissions"]
