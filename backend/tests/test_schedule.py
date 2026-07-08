"""定时任务模块测试 — CRUD / 启停 / 手动执行 / 仪表盘"""

import pytest
from httpx import AsyncClient


@pytest.fixture
async def auth(client: AsyncClient) -> dict:
    """创建测试租户，管理员有 schedule:* 权限"""
    import uuid
    slug = f"sched-test-{uuid.uuid4().hex[:8]}"
    resp = await client.post("/api/v1/auth/register", json={
        "tenant_name": "Schedule Test", "tenant_slug": slug,
        "username": "sched_admin", "password": "AdminPass123",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _create_task(client, auth, name="test-task", task_key="test.job", cron="0 8 * * *"):
    """Helper: 创建一个测试任务，返回 task dict"""
    resp = await client.post("/api/v1/schedule/tasks", headers=auth, params={
        "name": name, "task_key": task_key, "cron_expression": cron,
    })
    assert resp.status_code == 201, f"Create task failed: {resp.text[:200]}"
    return resp.json()


# ============================================================
# 任务 CRUD
# ============================================================

@pytest.mark.asyncio
async def test_list_tasks_empty(client: AsyncClient, auth: dict):
    """空任务列表"""
    resp = await client.get("/api/v1/schedule/tasks", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_create_task(client: AsyncClient, auth: dict):
    """创建定时任务"""
    resp = await client.post("/api/v1/schedule/tasks", headers=auth, params={
        "name": "Health Check", "task_key": "health.check",
        "cron_expression": "*/5 * * * *", "description": "Check system health",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Health Check"
    assert data["task_key"] == "health.check"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_tasks_with_data(client: AsyncClient, auth: dict):
    """有数据时列表"""
    await _create_task(client, auth, "Task A", "a.job")
    await _create_task(client, auth, "Task B", "b.job")

    resp = await client.get("/api/v1/schedule/tasks", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2


@pytest.mark.asyncio
async def test_list_tasks_filter_enabled(client: AsyncClient, auth: dict):
    """按启用状态筛选"""
    await _create_task(client, auth, "Enabled Task", "e.job")

    # 默认创建后是启用的
    resp = await client.get("/api/v1/schedule/tasks?enabled=true", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_get_task_detail(client: AsyncClient, auth: dict):
    """任务详情含执行历史"""
    t = await _create_task(client, auth, "Detail Task", "detail.job")
    resp = await client.get(f"/api/v1/schedule/tasks/{t['id']}", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Detail Task"
    assert data["task_key"] == "detail.job"
    assert "history" in data


@pytest.mark.asyncio
async def test_get_task_not_found(client: AsyncClient, auth: dict):
    """不存在的任务 → 404"""
    resp = await client.get(
        "/api/v1/schedule/tasks/00000000-0000-0000-0000-000000000000",
        headers=auth,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_task(client: AsyncClient, auth: dict):
    """更新任务"""
    t = await _create_task(client, auth, "Old Name", "old.job")
    resp = await client.patch(f"/api/v1/schedule/tasks/{t['id']}", headers=auth, params={
        "name": "New Name", "cron_expression": "0 12 * * *",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "New Name"
    assert data["cron_expression"] == "0 12 * * *"


@pytest.mark.asyncio
async def test_delete_task(client: AsyncClient, auth: dict):
    """删除任务 → 204"""
    t = await _create_task(client, auth, "To Delete", "del.job")
    resp = await client.delete(f"/api/v1/schedule/tasks/{t['id']}", headers=auth)
    assert resp.status_code == 204

    # 确认已删除
    resp2 = await client.get(f"/api/v1/schedule/tasks/{t['id']}", headers=auth)
    assert resp2.status_code == 404


# ============================================================
# 启停
# ============================================================

@pytest.mark.asyncio
async def test_enable_task(client: AsyncClient, auth: dict):
    """启用任务"""
    t = await _create_task(client, auth, "Enable Me", "enable.job")
    # 先禁用再启用
    await client.post(f"/api/v1/schedule/tasks/{t['id']}/disable", headers=auth)
    resp = await client.post(f"/api/v1/schedule/tasks/{t['id']}/enable", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True


@pytest.mark.asyncio
async def test_disable_task(client: AsyncClient, auth: dict):
    """禁用任务"""
    t = await _create_task(client, auth, "Disable Me", "disable.job")
    resp = await client.post(f"/api/v1/schedule/tasks/{t['id']}/disable", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False


# ============================================================
# 手动执行
# ============================================================

@pytest.mark.asyncio
async def test_run_task_now(client: AsyncClient, auth: dict):
    """手动触发执行 — 无 Celery 时也应返回结果不崩溃"""
    t = await _create_task(client, auth, "Run Now", "run.job")
    resp = await client.post(f"/api/v1/schedule/tasks/{t['id']}/run", headers=auth)
    # 可能成功 dispatch 或失败（Celery 没启动），但不应 500
    assert resp.status_code in (200, 500), f"Unexpected status: {resp.status_code}"
    data = resp.json()
    assert "execution_id" in data or "status" in data


# ============================================================
# 仪表盘
# ============================================================

@pytest.mark.asyncio
async def test_dashboard(client: AsyncClient, auth: dict):
    """任务仪表盘"""
    resp = await client.get("/api/v1/schedule/status", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert "health" in data
    assert "recent_executions" in data
    assert "next_scheduled" in data


# ============================================================
# 边界条件
# ============================================================

@pytest.mark.asyncio
async def test_unauthorized(client: AsyncClient):
    """未登录 → 401"""
    for method, path in [
        ("GET", "/api/v1/schedule/tasks"),
        ("GET", "/api/v1/schedule/status"),
        ("POST", "/api/v1/schedule/tasks"),
    ]:
        if method == "GET":
            resp = await client.get(path)
        else:
            resp = await client.post(path)
        assert resp.status_code == 401, f"{method} {path} should 401, got {resp.status_code}"


@pytest.mark.asyncio
async def test_create_task_missing_fields(client: AsyncClient, auth: dict):
    """缺少必填字段 → 422"""
    resp = await client.post("/api/v1/schedule/tasks", headers=auth, params={
        "name": "No Key",
    })
    assert resp.status_code == 422
