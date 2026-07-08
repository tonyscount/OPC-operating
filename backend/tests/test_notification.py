"""通知 & 会话模块测试 — 列表/已读/未读数/会话管理"""

import uuid
import pytest
from httpx import AsyncClient


@pytest.fixture
async def auth(client: AsyncClient) -> dict:
    """创建测试租户并登录"""
    slug = f"notif-{uuid.uuid4().hex[:8]}"
    resp = await client.post("/api/v1/auth/register", json={
        "tenant_name": "Notif Test", "tenant_slug": slug,
        "username": "notif_user", "password": "NotifPass123",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _create_notification(user_id, tenant_id, title="Test", body="Body",
                                notif_type="system", urgency="normal"):
    """Helper: 通过 app 的 session factory 插入通知 (区别于测试的 rollback db)"""
    from app.core.database import async_session_factory
    from app.modules.notification.models import Notification

    async with async_session_factory() as sess:
        n = Notification(
            tenant_id=tenant_id, recipient_id=user_id,
            title=title, body=body,
            notification_type=notif_type, urgency=urgency,
        )
        sess.add(n)
        await sess.commit()
        await sess.refresh(n)
        return n


# ============================================================
# 通知
# ============================================================

@pytest.mark.asyncio
async def test_list_notifications_empty(client: AsyncClient, auth: dict):
    """空通知列表"""
    resp = await client.get("/api/v1/notifications", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_notifications_with_data(client: AsyncClient, auth: dict):
    """有通知数据时列表"""
    # 获取用户 ID
    me = await client.get("/api/v1/auth/me", headers=auth)
    user_id = uuid.UUID(me.json()["user_id"])
    tid = uuid.UUID(me.json()["tenant_id"])

    await _create_notification(user_id, tid, "Test 1", "Body 1")
    await _create_notification(user_id, tid, "Test 2", "Body 2", urgency="high")

    resp = await client.get("/api/v1/notifications", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    # 最新的在前
    assert data["items"][0]["urgency"] == "high"


@pytest.mark.asyncio
async def test_list_notifications_unread_only(client: AsyncClient, auth: dict):
    """按未读筛选"""
    me = await client.get("/api/v1/auth/me", headers=auth)
    user_id = uuid.UUID(me.json()["user_id"])
    tid = uuid.UUID(me.json()["tenant_id"])

    await _create_notification(user_id, tid, "Unread", "body")
    n2 = await _create_notification(user_id, tid, "Read", "body")
    # 标记 n2 已读 (通过 API)
    await client.patch(f"/api/v1/notifications/{n2.id}/read", headers=auth)

    resp = await client.get("/api/v1/notifications?unread_only=true", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Unread"


@pytest.mark.asyncio
async def test_unread_count(client: AsyncClient, auth: dict):
    """未读计数"""
    me = await client.get("/api/v1/auth/me", headers=auth)
    user_id = uuid.UUID(me.json()["user_id"])
    tid = uuid.UUID(me.json()["tenant_id"])

    await _create_notification(user_id, tid, "A", "a")
    await _create_notification(user_id, tid, "B", "b")
    await _create_notification(user_id, tid, "C", "c")

    resp = await client.get("/api/v1/notifications/unread-count", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["unread"] == 3


@pytest.mark.asyncio
async def test_mark_read(client: AsyncClient, auth: dict):
    """标记单条已读"""
    me = await client.get("/api/v1/auth/me", headers=auth)
    user_id = uuid.UUID(me.json()["user_id"])
    tid = uuid.UUID(me.json()["tenant_id"])

    n = await _create_notification(user_id, tid, "Mark Me", "body")

    resp = await client.patch(f"/api/v1/notifications/{n.id}/read", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["read"] is True

    # 确认已读
    resp2 = await client.get("/api/v1/notifications/unread-count", headers=auth)
    assert resp2.json()["unread"] == 0


@pytest.mark.asyncio
async def test_mark_read_other_user(client: AsyncClient, auth: dict):
    """标记别人的通知 — 不报错但不生效"""
    fake_id = uuid.uuid4()
    resp = await client.patch(f"/api/v1/notifications/{fake_id}/read", headers=auth)
    # 不存在的通知或别人的通知 — 幂等返回
    assert resp.status_code == 200
    assert resp.json()["read"] is True


@pytest.mark.asyncio
async def test_mark_all_read(client: AsyncClient, auth: dict):
    """全部已读"""
    me = await client.get("/api/v1/auth/me", headers=auth)
    user_id = uuid.UUID(me.json()["user_id"])
    tid = uuid.UUID(me.json()["tenant_id"])

    await _create_notification(user_id, tid, "A", "a")
    await _create_notification(user_id, tid, "B", "b")

    resp = await client.post("/api/v1/notifications/read-all", headers=auth)
    assert resp.status_code == 200

    # 确认全部已读
    resp2 = await client.get("/api/v1/notifications/unread-count", headers=auth)
    assert resp2.json()["unread"] == 0


# ============================================================
# 会话
# ============================================================

@pytest.mark.asyncio
async def test_list_conversations_empty(client: AsyncClient, auth: dict):
    """空会话列表"""
    resp = await client.get("/api/v1/conversations", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_create_conversation_fake_user(client: AsyncClient, auth: dict):
    """创建会话 — 不存在的用户 → FK 约束报错 (已知问题，应加用户校验)"""
    fake_id = uuid.uuid4()
    resp = await client.post("/api/v1/conversations", headers=auth,
                             params={"with_user_id": str(fake_id), "title": "Test Chat"})
    # 修复前: NotNullViolation (tenant_id 缺失 → 500)
    # 修复后: NotFoundException (用户不存在 → 404)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_messages_forbidden(client: AsyncClient, auth: dict):
    """非参与者无权访问会话消息 → 403"""
    resp = await client.get(
        f"/api/v1/conversations/{uuid.uuid4()}/messages", headers=auth,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_total_unread(client: AsyncClient, auth: dict):
    """总未读数 — 空"""
    resp = await client.get("/api/v1/conversations/unread-total", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["unread"] == 0


# ============================================================
# 边界条件
# ============================================================

@pytest.mark.asyncio
async def test_unauthorized(client: AsyncClient):
    """所有端点未登录 → 401"""
    paths = [
        "/api/v1/notifications",
        "/api/v1/notifications/unread-count",
    ]
    for path in paths:
        resp = await client.get(path)
        assert resp.status_code == 401, f"GET {path} should 401, got {resp.status_code}"

    resp = await client.patch(f"/api/v1/notifications/{uuid.uuid4()}/read")
    assert resp.status_code == 401

    resp = await client.post("/api/v1/notifications/read-all")
    assert resp.status_code == 401
