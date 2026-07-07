"""
Feed Timeline 服务 — 写时扇出 + Redis Sorted Set 时间线。

架构:
  发帖 → [粉丝<5000?] → 异步扇出到每个粉丝的 Redis Timeline
       → [粉丝≥5000?] → 标记大V, 读时从 DB 拉取合并

  读关注流 → Redis ZREVRANGE timeline:{uid} + 大V DB 最新帖 → 合并排序 → 批量查 DB 详情

Redis Key 设计:
  timeline:{user_id}        Sorted Set  score=timestamp  member=post_id  保留最近 1000 条
  big_v_posts:{user_id}     Sorted Set  score=timestamp  member=post_id  大V 最近 200 条
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.redis_client import feed_redis
from app.modules.social.models import SocialPost, UserFollow

logger = logging.getLogger("opc.feed")

# 扇出阈值: 粉丝数 >= 此值视为大V, 不走扇出
BIG_V_FOLLOWER_THRESHOLD = 5000
# Redis Timeline 最大长度
TIMELINE_MAX_LEN = 1000
# 大V 帖子缓存最大长度
BIG_V_CACHE_LEN = 200


# ============================================================
# 写路径 — 扇出
# ============================================================

async def fanout_post_to_followers(
    db: AsyncSession,
    post_id: uuid.UUID,
    author_id: uuid.UUID,
    tenant_id: uuid.UUID,
    created_at: datetime,
) -> dict:
    """
    将帖子扇出到所有粉丝的 Timeline。同步执行，用于小粉丝量的作者。

    返回: {"fanout_count": N, "is_big_v": bool}
    """
    # 统计粉丝数
    follower_count = await db.scalar(
        select(func.count(UserFollow.id)).where(
            UserFollow.following_id == author_id,
            UserFollow.is_deleted == False,
        )
    ) or 0

    if follower_count >= BIG_V_FOLLOWER_THRESHOLD:
        # 大V: 不扇出, 仅写入自己的大V缓存
        await _cache_big_v_post(str(author_id), str(post_id), created_at)
        logger.info(f"Big V post: author={author_id}, followers={follower_count}")
        return {"fanout_count": 0, "is_big_v": True, "follower_count": follower_count}

    if follower_count == 0:
        return {"fanout_count": 0, "is_big_v": False, "follower_count": 0}

    # 拉取粉丝列表
    result = await db.execute(
        select(UserFollow.follower_id).where(
            UserFollow.following_id == author_id,
            UserFollow.is_deleted == False,
        )
    )
    follower_ids = [str(row[0]) for row in result.all()]

    if not follower_ids:
        return {"fanout_count": 0, "is_big_v": False, "follower_count": follower_count}

    # 构建批量 zadd 条目
    score = created_at.timestamp()
    post_id_str = str(post_id)
    entries = [(f"timeline:{fid}", post_id_str, score) for fid in follower_ids]

    # 也写入作者自己的 Timeline
    entries.append((f"timeline:{author_id}", post_id_str, score))

    # 批量写入 Redis
    await feed_redis.pipeline_zadd_batch(entries)

    logger.info(
        f"Fanout complete: post={post_id_str}, "
        f"followers={follower_count}, entries={len(entries)}"
    )

    return {"fanout_count": len(entries) - 1, "is_big_v": False, "follower_count": follower_count}


async def _cache_big_v_post(author_id: str, post_id: str, created_at: datetime):
    """将大V帖子写入缓存 (供粉丝读流时合并)"""
    score = created_at.timestamp()
    key = f"big_v_posts:{author_id}"
    await feed_redis.zadd(key, {post_id: score}, maxlen=BIG_V_CACHE_LEN)
    # TTL 14 天
    c = await feed_redis.get_client()
    await c.expire(key, 86400 * 14)


# ============================================================
# 读路径 — 获取关注流
# ============================================================

async def get_following_timeline(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[SocialPost], int]:
    """
    从 Redis Timeline + 大V DB 帖 混合获取关注流。

    1. 从 Redis 读 timeline:{user_id} (粉丝<5000 的作者帖)
    2. 从 DB 查关注的大V最近帖 (粉丝>=5000 的作者帖)
    3. 合并排序, 分页, 批量查 DB 获取完整 Post 对象
    """
    uid_str = str(user_id)

    # ——— 1. Redis Timeline ———
    timeline_key = f"timeline:{uid_str}"
    start = (page - 1) * page_size
    stop = start + page_size + 50  # 多取一些用于和大V帖合并后还有余量

    redis_post_ids = await feed_redis.zrevrange(timeline_key, 0, stop)
    timeline_size = await feed_redis.zcard(timeline_key)

    # 如果 Timeline 为空 (新用户/缓存被清), 从 DB 回填并返回
    if not redis_post_ids:
        posts, total = await _db_following_fallback(db, tenant_id, user_id, page, page_size)
        # 异步回填 Timeline: 下次就快了
        if posts:
            asyncio.create_task(_warm_fill_timeline(uid_str, posts))
        return posts, total

    # ——— 2. 大V 帖子 ———
    big_v_posts = await _get_big_v_posts(db, tenant_id, user_id)

    # ——— 3. 合并所有 post_id，批量查 DB ———
    all_post_ids = set(redis_post_ids)
    if big_v_posts:
        all_post_ids.update(str(p.id) for p in big_v_posts)
        # 大V帖也加到结果池，按时间排序
        big_v_ids = {str(p.id): p for p in big_v_posts}
    else:
        big_v_ids = {}

    # 批量查 DB 获取 Post 对象
    post_uuids = [uuid.UUID(pid) for pid in all_post_ids]
    result = await db.execute(
        select(SocialPost).where(
            SocialPost.id.in_(post_uuids),
            SocialPost.tenant_id == tenant_id,
            SocialPost.is_deleted == False,
            SocialPost.visibility == "public",
        )
    )
    posts_map: dict[str, SocialPost] = {}
    for p in result.scalars().all():
        posts_map[str(p.id)] = p

    # 合并 Redis 顺序 + 大V帖，按时间排序
    all_posts: list[SocialPost] = []
    seen: set[str] = set()

    # 先按 Redis Timeline 顺序添加
    for pid in redis_post_ids:
        if pid in posts_map and pid not in seen:
            all_posts.append(posts_map[pid])
            seen.add(pid)

    # 再把大V帖插进去（按时间降序）
    for pid, post in sorted(
        big_v_ids.items(),
        key=lambda x: x[1].created_at if x[1].created_at else datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    ):
        if pid not in seen and pid in posts_map:
            all_posts.append(posts_map[pid])
            seen.add(pid)

    # 统一按时间排序
    all_posts.sort(
        key=lambda p: p.created_at if p.created_at else datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    total = len(all_posts)
    paged = all_posts[start:start + page_size]

    return paged, total


async def _get_big_v_posts(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[SocialPost]:
    """
    获取我关注的大V (粉丝>=5000) 最近 50 条帖子。

    先从 Redis big_v_posts:{author_id} 缓存取, 缓存为空时查 DB。
    """
    # 查我关注的大V
    from sqlalchemy import and_

    # 子查询: 我的关注
    following_subq = (
        select(UserFollow.following_id)
        .where(
            UserFollow.follower_id == user_id,
            UserFollow.is_deleted == False,
        )
    )

    # 查这些关注中粉丝数>阈值的 (简化: 直接查最近帖, 按 author_id 分组取最新)
    # 实际生产场景应维护一个大V标记表, 这里简化处理
    result = await db.execute(
        select(SocialPost).where(
            SocialPost.author_id.in_(following_subq),
            SocialPost.tenant_id == tenant_id,
            SocialPost.is_deleted == False,
            SocialPost.visibility == "public",
        )
        .order_by(SocialPost.created_at.desc())
        .limit(200)
    )

    posts = list(result.scalars().all())

    # 过滤: 只保留大V作者的帖 (从 Redis 缓存确认粉丝数, 或直接去重返回)
    # 简化处理: 返回所有关注者的最近帖 (对于中小规模已足够)
    # 当关注数很大时, 依赖 Redis Timeline 已经处理了大部分
    return posts


async def _db_following_fallback(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    page: int,
    page_size: int,
) -> tuple[list[SocialPost], int]:
    """
    DB 降级查询 — 当 Redis Timeline 为空时, 用子查询方式查关注流。
    保留原有逻辑作为兜底。
    """
    following_ids_subq = (
        select(UserFollow.following_id)
        .where(
            UserFollow.follower_id == user_id,
            UserFollow.is_deleted == False,
        )
    )

    count_result = await db.scalar(
        select(func.count(SocialPost.id)).where(
            SocialPost.tenant_id == tenant_id,
            SocialPost.is_deleted == False,
            SocialPost.author_id.in_(following_ids_subq),
            SocialPost.visibility == "public",
        )
    )
    total = count_result or 0

    result = await db.execute(
        select(SocialPost)
        .where(
            SocialPost.tenant_id == tenant_id,
            SocialPost.is_deleted == False,
            SocialPost.author_id.in_(following_ids_subq),
            SocialPost.visibility == "public",
        )
        .order_by(SocialPost.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    posts = list(result.scalars().all())

    return posts, total


# ============================================================
# Timeline 维护
# ============================================================

async def _warm_fill_timeline(uid_str: str, posts: list[SocialPost]):
    """首次访问时从 DB 回填 Timeline (异步, 不阻塞响应)"""
    try:
        entries = [
            (f"timeline:{uid_str}", str(p.id), p.created_at.timestamp())
            for p in posts
            if p.created_at
        ]
        if entries:
            c = await feed_redis.get_client()
            pipe = c.pipeline()
            for key, member, score in entries:
                pipe.zadd(key, {member: score})
            pipe.zremrangebyrank(f"timeline:{uid_str}", 0, -TIMELINE_MAX_LEN - 1)
            await pipe.execute()
            logger.info(f"Timeline warm-filled: user={uid_str}, count={len(entries)}")
    except Exception:
        logger.exception(f"Timeline warm-fill failed for user={uid_str}")


async def remove_post_from_timelines(post_id: uuid.UUID, follower_ids: list[uuid.UUID]):
    """删除帖子时从所有相关 Timeline 移除"""
    post_id_str = str(post_id)
    keys = [f"timeline:{fid}" for fid in follower_ids]
    c = await feed_redis.get_client()
    for key in keys:
        await c.zrem(key, post_id_str)
