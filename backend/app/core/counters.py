"""
Redis 原子计数器 — 点赞/评论/浏览计数

设计:
  - Redis INCR/DECR 原子操作, 毫秒级响应
  - 每 30s 批量同步 Redis → DB (Celery beat)
  - Redis 不可用时降级到 DB 直写

Key 设计:
  counter:post:{id}:likes     String  点赞数
  counter:post:{id}:comments  String  评论数
  counter:post:{id}:views     String  浏览数
  likers:{post_id}            Set     点赞用户集合 (防重复)

用法:
    from app.core.counters import like_counter

    await like_counter.incr(post_id)       # 点赞 +1
    await like_counter.decr(post_id)       # 取消赞 -1
    count = await like_counter.get(post_id) # 读当前值
"""

import logging
from typing import Optional

from app.core.redis_client import RedisClient

logger = logging.getLogger("opc.counters")

# DB 5: 计数器
counter_redis = RedisClient(db=5, name="counters")

SYNC_INTERVAL = 30  # 秒


class PostCounter:
    """帖子的原子计数器 — likes / comments / views"""

    def __init__(self, counter_type: str):
        self.type = counter_type  # "likes" | "comments" | "views"
        self._prefix = f"counter:post:"

    def _key(self, post_id: str) -> str:
        return f"{self._prefix}{post_id}:{self.type}"

    # ——— 写 ———

    async def incr(self, post_id: str, amount: int = 1) -> int:
        """原子递增, 返回新值"""
        try:
            c = await counter_redis.get_client()
            return await c.incrby(self._key(post_id), amount)
        except Exception:
            return -1

    async def decr(self, post_id: str, amount: int = 1) -> int:
        """原子递减, 返回新值 (最少为 0)"""
        try:
            c = await counter_redis.get_client()
            val = await c.decrby(self._key(post_id), amount)
            if val < 0:
                await c.set(self._key(post_id), 0)
                return 0
            return val
        except Exception:
            return -1

    # ——— 读 ———

    async def get(self, post_id: str) -> Optional[int]:
        """读取当前计数"""
        try:
            c = await counter_redis.get_client()
            raw = await c.get(self._key(post_id))
            return int(raw) if raw else 0
        except Exception:
            return None  # 调用方应 fallback 到 DB

    async def get_bulk(self, post_ids: list[str]) -> dict[str, int]:
        """批量读取计数"""
        if not post_ids:
            return {}
        try:
            c = await counter_redis.get_client()
            keys = [self._key(pid) for pid in post_ids]
            vals = await c.mget(keys)
            result = {}
            for pid, v in zip(post_ids, vals):
                result[pid] = int(v) if v else 0
            return result
        except Exception:
            # fallback: 全部返回 0, 调用方从 DB 补
            return {pid: 0 for pid in post_ids}

    # ——— 同步 ———

    async def get_all_dirty(self) -> dict[str, int]:
        """获取所有非零计数器 (用于批量同步到 DB)"""
        try:
            c = await counter_redis.get_client()
            dirty = {}
            pattern = f"{self._prefix}*:{self.type}"
            async for key in c.scan_iter(match=pattern, count=100):
                val = await c.get(key)
                if val and int(val) > 0:
                    # 从 key 中提取 post_id
                    # counter:post:{id}:likes → {id}
                    pid = key.split(":")[2]
                    dirty[pid] = int(val)
            return dirty
        except Exception:
            return {}

    async def reset(self, post_id: str) -> None:
        """同步后重置计数器 (不清零, 只删 key)"""
        try:
            c = await counter_redis.get_client()
            await c.delete(self._key(post_id))
        except Exception:
            pass


# ——— 全局实例 ———
like_counter = PostCounter("likes")
comment_counter = PostCounter("comments")
view_counter = PostCounter("views")


# ============================================================
# 点赞去重 Set
# ============================================================

class LikeSet:
    """点赞用户集合 — 防止重复点赞"""

    @staticmethod
    def _key(post_id: str) -> str:
        return f"likers:{post_id}"

    async def add(self, post_id: str, user_id: str) -> bool:
        """添加点赞用户。返回 True 表示首次点赞。"""
        try:
            c = await counter_redis.get_client()
            added = await c.sadd(self._key(post_id), user_id)
            return added == 1
        except Exception:
            return True  # Redis 不可用时信任 DB 唯一约束

    async def remove(self, post_id: str, user_id: str) -> bool:
        """移除点赞用户。返回 True 表示确实移除了。"""
        try:
            c = await counter_redis.get_client()
            removed = await c.srem(self._key(post_id), user_id)
            return removed == 1
        except Exception:
            return True

    async def is_liked(self, post_id: str, user_id: str) -> bool:
        """检查用户是否已点赞"""
        try:
            c = await counter_redis.get_client()
            return await c.sismember(self._key(post_id), user_id)
        except Exception:
            return False

    async def check_bulk(self, post_ids: list[str], user_id: str) -> set[str]:
        """批量检查用户对哪些帖子点赞了"""
        if not post_ids:
            return set()
        try:
            c = await counter_redis.get_client()
            pipe = c.pipeline()
            for pid in post_ids:
                pipe.sismember(self._key(pid), user_id)
            results = await pipe.execute()
            return {pid for pid, liked in zip(post_ids, results) if liked}
        except Exception:
            return set()


like_set = LikeSet()
