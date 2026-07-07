"""
社交模块 — 业务逻辑层

所有操作用 UUID 确保类型安全，避免跨租户操作。
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.modules.social.models import (
    SocialComment,
    SocialLike,
    SocialPost,
    UserFollow,
    UserFriend,
)
from app.modules.tenant.models import User


# ============================================================
# 动态 (Post)
# ============================================================

async def create_post(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    author_id: uuid.UUID,
    *,
    content: str,
    media_urls: list[str] | None = None,
    visibility: str = "public",
) -> SocialPost:
    """发布动态"""
    post = SocialPost(
        tenant_id=tenant_id,
        author_id=author_id,
        content=content,
        media_urls=media_urls,
        visibility=visibility,
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return post


async def get_post(db: AsyncSession, tenant_id: uuid.UUID, post_id: uuid.UUID) -> SocialPost:
    """获取动态详情"""
    result = await db.execute(
        select(SocialPost).where(
            SocialPost.id == post_id,
            SocialPost.tenant_id == tenant_id,
            SocialPost.is_deleted == False,
        )
    )
    post = result.scalar_one_or_none()
    if not post:
        raise NotFoundException("动态不存在")
    return post


async def get_feed(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    current_user_id: uuid.UUID,
    *,
    feed_type: str = "all",
    target_user_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[SocialPost], int]:
    """
    获取动态流。

    feed_type:
      - "all": 全站公开动态
      - "following": 我关注的人的动态
      - "user": 指定用户的动态
    """
    base_conditions = [
        SocialPost.tenant_id == tenant_id,
        SocialPost.is_deleted == False,
    ]

    if feed_type == "following":
        # 我关注的人的动态
        following_ids = (
            select(UserFollow.following_id)
            .where(UserFollow.follower_id == current_user_id)
        )
        base_conditions.append(SocialPost.author_id.in_(following_ids))
        base_conditions.append(SocialPost.visibility != "private")
    elif feed_type == "user" and target_user_id:
        base_conditions.append(SocialPost.author_id == target_user_id)
        # 看别人的动态：只显示公开的
        if target_user_id != current_user_id:
            base_conditions.append(SocialPost.visibility == "public")
    else:
        # "all" — 全站公开动态
        base_conditions.append(SocialPost.visibility == "public")

    # 计数
    count_result = await db.scalar(
        select(func.count(SocialPost.id)).where(*base_conditions)
    )
    total = count_result or 0

    # 查询
    result = await db.execute(
        select(SocialPost)
        .where(*base_conditions)
        .order_by(SocialPost.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    posts = list(result.scalars().all())

    return posts, total


async def update_post(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    post_id: uuid.UUID,
    author_id: uuid.UUID,
    **kwargs,
) -> SocialPost:
    """编辑动态 (仅作者本人)"""
    post = await get_post(db, tenant_id, post_id)
    if post.author_id != author_id:
        raise ForbiddenException("只能编辑自己的动态")

    for k, v in kwargs.items():
        if v is not None:
            setattr(post, k, v)

    await db.commit()
    await db.refresh(post)
    return post


async def delete_post(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    post_id: uuid.UUID,
    author_id: uuid.UUID,
) -> None:
    """软删除动态 (作者或管理员)"""
    post = await get_post(db, tenant_id, post_id)
    if post.author_id != author_id:
        raise ForbiddenException("只能删除自己的动态")

    post.is_deleted = True
    post.deleted_at = datetime.now(timezone.utc)
    await db.commit()


async def increment_view(db: AsyncSession, tenant_id: uuid.UUID, post_id: uuid.UUID) -> None:
    """增加浏览次数"""
    await db.execute(
        text("UPDATE social_posts SET view_count = view_count + 1 WHERE id = :id AND tenant_id = :tid"),
        {"id": post_id, "tid": tenant_id},
    )
    await db.commit()


# ============================================================
# 评论
# ============================================================

async def create_comment(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    post_id: uuid.UUID,
    author_id: uuid.UUID,
    *,
    content: str,
    parent_id: uuid.UUID | None = None,
) -> SocialComment:
    """发表评论 (或回复)"""
    # 确保动态存在
    await get_post(db, tenant_id, post_id)

    if parent_id:
        parent = await db.scalar(
            select(SocialComment).where(
                SocialComment.id == parent_id,
                SocialComment.post_id == post_id,
                SocialComment.tenant_id == tenant_id,
            )
        )
        if not parent:
            raise NotFoundException("父评论不存在")

    comment = SocialComment(
        tenant_id=tenant_id,
        post_id=post_id,
        author_id=author_id,
        content=content,
        parent_id=parent_id,
    )
    db.add(comment)

    # 更新帖子评论数
    await db.execute(
        text("UPDATE social_posts SET comment_count = comment_count + 1 WHERE id = :id"),
        {"id": post_id},
    )

    await db.commit()
    await db.refresh(comment)
    return comment


async def get_comments(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    post_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[SocialComment], int]:
    """获取动态的评论列表 (一级评论)"""
    conditions = [
        SocialComment.tenant_id == tenant_id,
        SocialComment.post_id == post_id,
        SocialComment.parent_id == None,  # 只要一级评论
        SocialComment.is_deleted == False,
    ]

    total = await db.scalar(select(func.count(SocialComment.id)).where(*conditions))

    result = await db.execute(
        select(SocialComment)
        .where(*conditions)
        .order_by(SocialComment.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    comments = list(result.scalars().all())

    return comments, total or 0


async def get_comment_replies(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    comment_id: uuid.UUID,
) -> list[SocialComment]:
    """获取某条评论的子回复"""
    result = await db.execute(
        select(SocialComment).where(
            SocialComment.parent_id == comment_id,
            SocialComment.tenant_id == tenant_id,
            SocialComment.is_deleted == False,
        ).order_by(SocialComment.created_at.asc())
    )
    return list(result.scalars().all())


async def get_bulk_comment_replies(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    parent_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[SocialComment]]:
    """
    批量获取多条父评论的子回复 (解决 N+1 查询)。

    返回: {parent_id: [reply1, reply2, ...]}
    """
    if not parent_ids:
        return {}
    result = await db.execute(
        select(SocialComment).where(
            SocialComment.parent_id.in_(parent_ids),
            SocialComment.tenant_id == tenant_id,
            SocialComment.is_deleted == False,
        ).order_by(SocialComment.created_at.asc())
    )
    replies = list(result.scalars().all())
    grouped: dict[uuid.UUID, list[SocialComment]] = {}
    for r in replies:
        grouped.setdefault(r.parent_id, []).append(r)
    return grouped


# ============================================================
# 点赞
# ============================================================

async def toggle_like(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    target_type: str,
    target_id: uuid.UUID,
) -> dict:
    """
    切换点赞状态 — 赞过就取消，没赞就点赞。返回当前状态。
    """
    # 查找已有点赞
    existing = await db.scalar(
        select(SocialLike).where(
            SocialLike.user_id == user_id,
            SocialLike.target_type == target_type,
            SocialLike.target_id == target_id,
            SocialLike.tenant_id == tenant_id,
        )
    )

    if existing:
        # 取消点赞
        existing.is_deleted = True
        existing.deleted_at = datetime.now(timezone.utc)
        await db.commit()
        count_delta = -1
        is_liked = False
    else:
        # 点赞
        like = SocialLike(
            tenant_id=tenant_id,
            user_id=user_id,
            target_type=target_type,
            target_id=target_id,
        )
        db.add(like)
        await db.commit()
        count_delta = 1
        is_liked = True

    # 更新目标计数
    if target_type == "post":
        await db.execute(
            text("UPDATE social_posts SET like_count = like_count + :d WHERE id = :id"),
            {"d": count_delta, "id": target_id},
        )
        await db.commit()

    return {"is_liked": is_liked}


async def check_liked(
    db: AsyncSession,
    user_id: uuid.UUID,
    target_ids: list[uuid.UUID],
    target_type: str = "post",
) -> set[uuid.UUID]:
    """批量检查用户是否点赞了某些目标"""
    if not target_ids:
        return set()
    result = await db.execute(
        select(SocialLike.target_id).where(
            SocialLike.user_id == user_id,
            SocialLike.target_type == target_type,
            SocialLike.target_id.in_(target_ids),
            SocialLike.is_deleted == False,
        )
    )
    return {row[0] for row in result.all()}


# ============================================================
# 关注
# ============================================================

async def follow_user(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    follower_id: uuid.UUID,
    following_id: uuid.UUID,
) -> UserFollow:
    """关注用户"""
    if follower_id == following_id:
        raise ValidationException("不能关注自己")

    # 检查被关注者是否存在
    target = await db.get(User, following_id)
    if not target or target.tenant_id != tenant_id:
        raise NotFoundException("用户不存在")

    # 检查是否已关注
    existing = await db.scalar(
        select(UserFollow).where(
            UserFollow.follower_id == follower_id,
            UserFollow.following_id == following_id,
            UserFollow.is_deleted == False,
        )
    )
    if existing:
        raise ConflictException("已关注该用户")

    follow = UserFollow(
        tenant_id=tenant_id,
        follower_id=follower_id,
        following_id=following_id,
    )
    db.add(follow)
    await db.commit()
    await db.refresh(follow)
    return follow


async def unfollow_user(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    follower_id: uuid.UUID,
    following_id: uuid.UUID,
) -> None:
    """取消关注"""
    follow = await db.scalar(
        select(UserFollow).where(
            UserFollow.follower_id == follower_id,
            UserFollow.following_id == following_id,
            UserFollow.is_deleted == False,
        )
    )
    if not follow:
        raise NotFoundException("未关注该用户")

    follow.is_deleted = True
    follow.deleted_at = datetime.now(timezone.utc)
    await db.commit()


async def get_followers(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[User], int]:
    """获取粉丝列表"""
    subq = (
        select(UserFollow.follower_id)
        .where(UserFollow.following_id == user_id, UserFollow.is_deleted == False)
    )
    return await _paginate_users(db, tenant_id, subq, page, page_size)


async def get_following(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[User], int]:
    """获取关注列表"""
    subq = (
        select(UserFollow.following_id)
        .where(UserFollow.follower_id == user_id, UserFollow.is_deleted == False)
    )
    return await _paginate_users(db, tenant_id, subq, page, page_size)


# ============================================================
# 好友
# ============================================================

async def send_friend_request(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    from_user_id: uuid.UUID,
    to_user_id: uuid.UUID,
) -> UserFriend:
    """发送好友申请"""
    if from_user_id == to_user_id:
        raise ValidationException("不能添加自己为好友")

    # 检查目标用户
    target = await db.get(User, to_user_id)
    if not target or target.tenant_id != tenant_id:
        raise NotFoundException("用户不存在")

    # 检查是否已存在好友关系
    existing = await db.scalar(
        select(UserFriend).where(
            or_(
                and_(UserFriend.user_id == from_user_id, UserFriend.friend_id == to_user_id),
                and_(UserFriend.user_id == to_user_id, UserFriend.friend_id == from_user_id),
            ),
            UserFriend.is_deleted == False,
        )
    )
    if existing:
        if existing.status == "accepted":
            raise ConflictException("已经是好友")
        elif existing.status == "pending":
            raise ConflictException("好友申请已发送，等待对方确认")

    friend = UserFriend(
        tenant_id=tenant_id,
        user_id=from_user_id,
        friend_id=to_user_id,
        status="pending",
    )
    db.add(friend)
    await db.commit()
    await db.refresh(friend)
    return friend


async def handle_friend_request(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    current_user_id: uuid.UUID,
    friend_id: uuid.UUID,
    action: str,  # "accept" | "reject"
) -> UserFriend:
    """处理好友申请"""
    friend = await db.scalar(
        select(UserFriend).where(
            UserFriend.id == friend_id,
            UserFriend.friend_id == current_user_id,  # 我是被申请方
            UserFriend.status == "pending",
            UserFriend.is_deleted == False,
        )
    )
    if not friend:
        raise NotFoundException("好友申请不存在或已处理")

    if action == "accept":
        friend.status = "accepted"
        friend.accepted_at = datetime.now(timezone.utc)
    elif action == "reject":
        friend.status = "rejected"
    else:
        raise ValidationException("操作只能是 accept 或 reject")

    await db.commit()
    await db.refresh(friend)
    return friend


async def get_friends(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """获取好友列表"""
    conditions = [
        UserFriend.tenant_id == tenant_id,
        UserFriend.status == "accepted",
        UserFriend.is_deleted == False,
        or_(UserFriend.user_id == user_id, UserFriend.friend_id == user_id),
    ]

    total = await db.scalar(select(func.count(UserFriend.id)).where(*conditions))

    friends = (await db.execute(
        select(UserFriend).where(*conditions)
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    # 提取好友 user_id
    friend_user_ids = []
    for f in friends:
        fid = f.friend_id if f.user_id == user_id else f.user_id
        friend_user_ids.append(fid)

    # 批量查用户信息
    users_map = {}
    if friend_user_ids:
        user_results = await db.execute(
            select(User).where(User.id.in_(friend_user_ids))
        )
        users_map = {u.id: u for u in user_results.scalars().all()}

    result_list = []
    for f in friends:
        fid = f.friend_id if f.user_id == user_id else f.user_id
        u = users_map.get(fid)
        result_list.append({
            "id": f.id,
            "friend": {
                "id": str(fid),
                "username": u.username if u else "",
                "display_name": u.display_name if u else "",
                "avatar_url": u.avatar_url if u else None,
            },
            "accepted_at": f.accepted_at,
            "created_at": f.created_at,
        })

    return result_list, total or 0


# ============================================================
# 辅助
# ============================================================

async def _paginate_users(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    subquery,
    page: int,
    page_size: int,
) -> tuple[list[User], int]:
    """分页查询用户列表"""
    total = await db.scalar(select(func.count()).select_from(subquery.subquery()))
    users = (await db.execute(
        select(User).where(
            User.id.in_(subquery),
            User.tenant_id == tenant_id,
        ).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return list(users), total or 0
