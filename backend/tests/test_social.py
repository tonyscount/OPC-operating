"""社交模块测试"""

import pytest
from httpx import AsyncClient


@pytest.fixture
async def two_users(client: AsyncClient) -> tuple[dict, dict, dict]:
    """创建两个用户并返回各自的 header 和 user_id"""
    import uuid
    slug = f"social-test-{uuid.uuid4().hex[:8]}"
    # 用户 A
    r1 = await client.post("/api/v1/auth/register", json={
        "tenant_name": "Social Test", "tenant_slug": slug,
        "username": "user_a", "password": "pass123456",
    })
    token_a = r1.json()["access_token"]
    me_a = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_a}"})
    user_a_id = me_a.json()["user_id"]

    # 获取成员角色
    roles = await client.get("/api/v1/tenant/roles", headers={"Authorization": f"Bearer {token_a}"})
    member_role_id = None
    for r in roles.json():
        if r["name"] == "成员":
            member_role_id = r["id"]
            break

    # 用户 B (在同一租户下)
    resp = await client.post("/api/v1/tenant/users", json={
        "username": "user_b", "password": "pass123456",
        "display_name": "User B", "role_ids": [member_role_id] if member_role_id else [],
    }, headers={"Authorization": f"Bearer {token_a}"})
    user_b_id = resp.json()["id"]

    # 用户 B 登录 (使用注册时的 slug)
    r2 = await client.post("/api/v1/auth/login", json={
        "tenant_slug": slug, "username": "user_b", "password": "pass123456",
    })
    token_b = r2.json()["access_token"]

    return (
        {"Authorization": f"Bearer {token_a}", "user_id": user_a_id},
        {"Authorization": f"Bearer {token_b}", "user_id": user_b_id},
        member_role_id,
    )


@pytest.mark.asyncio
async def test_create_post(client: AsyncClient, two_users):
    """发布动态"""
    a, b, _ = two_users
    resp = await client.post("/api/v1/social/posts", json={
        "content": "Hello World!",
        "visibility": "public",
    }, headers=a)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_get_feed(client: AsyncClient, two_users):
    """获取动态列表"""
    a, b, _ = two_users
    # 发布几条动态
    for i in range(3):
        await client.post("/api/v1/social/posts", json={
            "content": f"Post {i}", "visibility": "public",
        }, headers=a)

    resp = await client.get("/api/v1/social/posts", headers=b)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 3
    assert len(data["items"]) >= 3


@pytest.mark.asyncio
async def test_private_post_not_in_public_feed(client: AsyncClient, two_users):
    """私密动态不出现在公开时间线"""
    a, b, _ = two_users
    await client.post("/api/v1/social/posts", json={
        "content": "Private post", "visibility": "private",
    }, headers=a)

    resp = await client.get("/api/v1/social/posts", headers=b)
    data = resp.json()
    contents = [item["content"] for item in data["items"]]
    assert "Private post" not in contents


@pytest.mark.asyncio
async def test_cannot_edit_others_post(client: AsyncClient, two_users):
    """非作者不能编辑别人的动态"""
    a, b, _ = two_users
    r = await client.post("/api/v1/social/posts", json={
        "content": "My post", "visibility": "public",
    }, headers=a)
    post_id = r.json()["id"]

    resp = await client.patch(f"/api/v1/social/posts/{post_id}", json={
        "content": "Hacked!"
    }, headers=b)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_comment_on_post(client: AsyncClient, two_users):
    """发表评论"""
    a, b, _ = two_users
    r = await client.post("/api/v1/social/posts", json={
        "content": "Commentable", "visibility": "public",
    }, headers=a)
    post_id = r.json()["id"]

    resp = await client.post(f"/api/v1/social/posts/{post_id}/comments", data={
        "content": "Nice post!",
    }, headers=b)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_toggle_like(client: AsyncClient, two_users):
    """点赞/取消点赞"""
    a, b, _ = two_users
    r = await client.post("/api/v1/social/posts", json={
        "content": "Like me", "visibility": "public",
    }, headers=a)
    post_id = r.json()["id"]

    # 点赞
    resp = await client.post(f"/api/v1/social/posts/{post_id}/like", headers=b)
    assert resp.status_code == 200
    assert resp.json()["is_liked"] == True

    # 再次请求 = 取消点赞
    resp = await client.post(f"/api/v1/social/posts/{post_id}/like", headers=b)
    assert resp.status_code == 200
    assert resp.json()["is_liked"] == False


@pytest.mark.asyncio
async def test_follow_and_unfollow(client: AsyncClient, two_users):
    """关注/取消关注"""
    a, b, _ = two_users
    user_a_id = a["user_id"]
    user_b_id = b["user_id"]

    # B 关注 A
    resp = await client.post(f"/api/v1/social/users/{user_a_id}/follow", headers=b)
    assert resp.status_code == 201

    # 查 A 的粉丝
    resp = await client.get(f"/api/v1/social/users/{user_a_id}/followers", headers=b)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1

    # 取消关注
    resp = await client.delete(f"/api/v1/social/users/{user_a_id}/follow", headers=b)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_cannot_follow_self(client: AsyncClient, two_users):
    """不能关注自己"""
    a, b, _ = two_users
    resp = await client.post(f"/api/v1/social/users/{a['user_id']}/follow", headers=a)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_friend_request_flow(client: AsyncClient, two_users):
    """完整好友申请流程"""
    a, b, _ = two_users
    user_a_id = a["user_id"]
    user_b_id = b["user_id"]

    # A 向 B 发送好友申请
    resp = await client.post("/api/v1/social/friends/request", json={
        "friend_id": user_b_id,
    }, headers=a)
    assert resp.status_code == 201
    friend_id = resp.json()["id"]

    # B 接受
    resp = await client.post(f"/api/v1/social/friends/{friend_id}/accept", headers=b)
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"

    # 查 A 的好友列表
    resp = await client.get("/api/v1/social/friends", headers=a)
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["friend"]["id"] == user_b_id


@pytest.mark.asyncio
async def test_search_users(client: AsyncClient, two_users):
    """搜索用户"""
    a, b, _ = two_users
    resp = await client.get("/api/v1/users/search?q=user_b", headers=a)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    usernames = [u["username"] for u in data["items"]]
    assert "user_b" in usernames
