"""
Redis 异步客户端 — 统一管理 Redis 连接，按 DB 编号隔离用途。

DB 分配:
  - DB 0: Celery broker / result backend
  - DB 1: Rate limiting (slowapi)
  - DB 2: Feed timeline + post cache + like counters
  - DB 3: Session / temporary data

用法:
    from app.core.redis_client import feed_redis

    # Timeline 操作
    await feed_redis.zadd(f"timeline:{user_id}", {post_id: timestamp})
    posts = await feed_redis.zrevrange(f"timeline:{user_id}", 0, 19)
"""

import logging
from typing import Optional

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger("opc.redis")


class RedisClient:
    """按 DB 编号隔离的 Redis 异步客户端"""

    def __init__(self, db: int = 2, name: str = "default"):
        self.db = db
        self.name = name
        self._client: Optional[aioredis.Redis] = None

    async def get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.from_url(
                settings.REDIS_URL,
                db=self.db,
                decode_responses=True,
                protocol=2,  # Redis 3.x on Windows 不支持 RESP3
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=30,
            )
            logger.info(f"Redis[{self.name}] connected: DB {self.db}")
        return self._client

    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None
            logger.info(f"Redis[{self.name}] closed")

    # ---- Sorted Set 快捷方法 ----

    async def zadd(self, key: str, mapping: dict, maxlen: int | None = None) -> int:
        """向 Sorted Set 添加条目，可选裁剪到 maxlen"""
        c = await self.get_client()
        added = await c.zadd(key, mapping)
        if maxlen is not None:
            # 保留最新的 maxlen 条 (score 越大越新)
            await c.zremrangebyrank(key, 0, -maxlen - 1)
        return added

    async def zrevrange(
        self, key: str, start: int, stop: int, withscores: bool = False
    ) -> list:
        """倒序取 Sorted Set (最新的在前)"""
        c = await self.get_client()
        return await c.zrevrange(key, start, stop, withscores=withscores)

    async def delete(self, *keys: str) -> int:
        c = await self.get_client()
        return await c.delete(*keys)

    async def zcard(self, key: str) -> int:
        c = await self.get_client()
        return await c.zcard(key)

    async def zrem(self, key: str, *members: str) -> int:
        c = await self.get_client()
        return await c.zrem(key, *members)

    # ---- Pipeline 批量写入 ----

    async def pipeline_zadd_batch(
        self, entries: list[tuple[str, str, float]]
    ) -> None:
        """
        批量 zadd，格式: [(key, member, score), ...]。
        用于扇出时将一条帖子推入多个用户 Timeline。
        """
        c = await self.get_client()
        pipe = c.pipeline()
        for key, member, score in entries:
            pipe.zadd(key, {member: score})
            # 每个 Timeline 保留最近 1000 条
            pipe.zremrangebyrank(key, 0, -1001)
        await pipe.execute()


# ---- 全局单例 ----

# Feed Timeline (DB 2)
feed_redis = RedisClient(db=2, name="feed")

# 帖子缓存 (DB 2 — 共用 feed_redis 的连接池)
post_cache = RedisClient(db=2, name="post_cache")
