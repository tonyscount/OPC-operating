"""
用户模块 — 业务逻辑层

- 个人资料管理
- 密码修改
- 隐私设置
- 用户搜索/发现
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get, cache_set, cache_delete, user_key, stats_key
from app.core.exceptions import (
    ConflictException,
    NotFoundException,
    ValidationException,
)
from app.core.security import hash_password, verify_password
from app.modules.social.models import UserFollow, UserFriend
from app.modules.tenant.models import Organization, User, UserRole


# ============================================================
# 个人资料
# ============================================================

async def get_profile(
    db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID,
) -> dict:
    """获取用户完整资料 (含社交统计, 缓存 10min)"""
    uid_str = str(user_id)
    key = user_key(uid_str)

    cached = await cache_get(key)
    if cached:
        return cached

    user = await db.get(User, user_id)
    if not user or user.tenant_id != tenant_id:
        raise NotFoundException("用户不存在")

    # 组织名称
    org_name = None
    if user.org_id:
        org = await db.get(Organization, user.org_id)
        if org:
            org_name = org.name

    # 角色
    result = await db.execute(
        select(UserRole).where(UserRole.user_id == user_id)
    )
    user_roles = result.scalars().all()
    role_names = []
    for ur in user_roles:
        from sqlalchemy.orm import selectinload
        # 简单查角色名
        pass

    # 社交统计
    # TODO: 从 social_posts 统计帖子数
    post_count = 0

    follower_count = await db.scalar(
        select(func.count(UserFollow.id)).where(
            UserFollow.following_id == user_id,
            UserFollow.is_deleted == False,
        )
    )
    following_count = await db.scalar(
        select(func.count(UserFollow.id)).where(
            UserFollow.follower_id == user_id,
            UserFollow.is_deleted == False,
        )
    )

    return {
        "id": str(user.id),
        "tenant_id": str(user.tenant_id),
        "org_id": str(user.org_id) if user.org_id else None,
        "org_name": org_name,
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
        "phone": user.phone,
        "avatar_url": user.avatar_url,
        "bio": getattr(user, "bio", None),
        "status": user.status,
        "roles": role_names,
        "privacy": getattr(user, "privacy", {}),
        "stats": {
            "posts": 0,  # TODO
            "followers": follower_count or 0,
            "following": following_count or 0,
        },
        "created_at": user.created_at.isoformat(),
    }


async def update_profile(
    db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID, **kwargs,
) -> User:
    """更新个人资料"""
    user = await db.get(User, user_id)
    if not user or user.tenant_id != tenant_id:
        raise NotFoundException("用户不存在")

    # 邮箱唯一性检查
    if "email" in kwargs and kwargs["email"]:
        existing = await db.scalar(
            select(User).where(
                User.tenant_id == tenant_id,
                User.email == kwargs["email"],
                User.id != user_id,
            )
        )
        if existing:
            raise ConflictException("该邮箱已被使用")

    for k, v in kwargs.items():
        if v is not None:
            setattr(user, k, v)

    await db.commit()
    await db.refresh(user)
    return user


async def change_password(
    db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID,
    old_password: str, new_password: str,
) -> None:
    """修改密码"""
    user = await db.get(User, user_id)
    if not user or user.tenant_id != tenant_id:
        raise NotFoundException("用户不存在")

    if not verify_password(old_password, user.password_hash):
        raise ValidationException("原密码错误")

    user.password_hash = hash_password(new_password)
    await db.commit()


# ============================================================
# 用户搜索/发现
# ============================================================

async def search_users(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    current_user_id: uuid.UUID | None = None,
    *,
    keyword: str,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """搜索用户 (按用户名/显示名/邮箱)"""
    like = f"%{keyword}%"
    conditions = [
        User.tenant_id == tenant_id,
        User.status == "active",
        User.is_deleted == False,
        or_(
            User.username.ilike(like),
            User.display_name.ilike(like),
            User.email.ilike(like),
        ),
    ]

    total = await db.scalar(select(func.count(User.id)).where(*conditions))

    users = (await db.execute(
        select(User).where(*conditions)
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    # 检查当前用户是否已关注/已是好友
    following_set: set[uuid.UUID] = set()
    friend_set: set[uuid.UUID] = set()
    if current_user_id and users:
        user_ids = [u.id for u in users]
        # 关注关系
        follows = await db.execute(
            select(UserFollow.following_id).where(
                UserFollow.follower_id == current_user_id,
                UserFollow.following_id.in_(user_ids),
                UserFollow.is_deleted == False,
            )
        )
        following_set = {r[0] for r in follows.all()}
        # 好友关系
        friends = await db.execute(
            select(UserFriend.user_id, UserFriend.friend_id).where(
                UserFriend.tenant_id == tenant_id,
                UserFriend.status == "accepted",
                UserFriend.is_deleted == False,
                or_(
                    UserFriend.user_id == current_user_id,
                    UserFriend.friend_id == current_user_id,
                ),
            )
        )
        for row in friends.all():
            fid = row[1] if row[0] == current_user_id else row[0]
            friend_set.add(fid)

    items = []
    for u in users:
        items.append({
            "id": str(u.id),
            "username": u.username,
            "display_name": u.display_name,
            "avatar_url": u.avatar_url,
            "is_following": u.id in following_set,
            "is_friend": u.id in friend_set,
        })

    return items, total or 0
