"""
多级缓存层 — Redis Cache-Aside 模式

架构:
  读: Redis → 命中返回 / 未命中查 DB → 回写 Redis
  写: 更新 DB → 删除相关缓存 key → 下次读时自动回填

Redis Key 命名:  cache:{domain}:{id}
TTL 策略:  帖子 5min / 用户 10min / Feed 30s / 统计 2min / 搜索 5min

用法:
    from app.core.cache import cache_get, cache_set, cache_delete, cache_delete_pattern

    # 读
    post = await cache_get(f"post:{post_id}", fetch_func=db_get, ttl=300)
    # 写后失效
    await cache_delete(f"post:{post_id}")
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable

from app.core.redis_client import RedisClient

logger = logging.getLogger("opc.cache")

# Prometheus metrics (lazy import to avoid circular deps)
def _incr_cache_hit():
    try:
        from app.core.metrics import cache_hits
        cache_hits.inc()
    except Exception:
        pass

def _incr_cache_miss():
    try:
        from app.core.metrics import cache_misses
        cache_misses.inc()
    except Exception:
        pass

# DB 3: 业务缓存
cache_redis = RedisClient(db=3, name="cache")

# ——— TTL 常量 (秒) ———
TTL_POST     = 300   # 5 min  帖子详情
TTL_USER     = 600   # 10 min 用户名片
TTL_FEED     = 30    # 30 sec 全站流首页
TTL_STATS    = 120   # 2 min  关注/粉丝计数
TTL_SEARCH   = 300   # 5 min  搜索结果


# ============================================================
# 核心缓存操作
# ============================================================

async def _redis_available() -> bool:
    """检测 Redis 是否可用 (不可用时静默降级)"""
    try:
        c = await cache_redis.get_client()
        await c.ping()
        return True
    except Exception:
        return False


async def cache_get(
    key: str,
    fetch_func: Callable = None,
    ttl: int = 300,
) -> Any:
    """
    缓存读取 (Cache-Aside)。Redis 不可用时透明降级到 fetch_func。
    """
    try:
        c = await cache_redis.get_client()
        raw = await c.get(key)
        if raw:
            _incr_cache_hit()
            logger.debug(f"Cache HIT: {key}")
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return raw
    except Exception:
        pass  # Redis 不可用 → 降级

    if fetch_func is None:
        return None

    _incr_cache_miss()
    logger.debug(f"Cache MISS: {key}")
    value = await fetch_func() if callable(fetch_func) else fetch_func

    # 尝试回写 (Redis 不可用时跳过)
    if value is not None:
        try:
            await cache_set(key, value, ttl)
        except Exception:
            pass

    return value


async def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    """写缓存 + 设 TTL。Redis 不可用时静默跳过。"""
    try:
        c = await cache_redis.get_client()
        try:
            raw = json.dumps(value, ensure_ascii=False, default=_json_serializer)
        except (TypeError, ValueError):
            raw = str(value)
        await c.setex(key, ttl, raw)
        logger.debug(f"Cache SET: {key} (TTL={ttl}s)")
    except Exception:
        pass


async def cache_delete(*keys: str) -> int:
    """删除缓存。Redis 不可用时静默跳过。"""
    if not keys:
        return 0
    try:
        c = await cache_redis.get_client()
        count = await c.delete(*keys)
        if count:
            logger.debug(f"Cache DEL: {', '.join(keys)}")
        return count
    except Exception:
        return 0


async def cache_delete_pattern(pattern: str) -> int:
    """按模式批量删缓存。Redis 不可用时静默跳过。"""
    try:
        c = await cache_redis.get_client()
        keys = []
        async for k in c.scan_iter(match=pattern, count=100):
            keys.append(k)
        if keys:
            return await c.delete(*keys)
    except Exception:
        pass
    return 0


async def cache_incr(key: str, amount: int = 1, ttl: int = TTL_STATS) -> int:
    """原子递增。Redis 不可用时返回 -1。"""
    try:
        c = await cache_redis.get_client()
        val = await c.incrby(key, amount)
        await c.expire(key, ttl)
        return val
    except Exception:
        return -1


def _json_serializer(obj):
    """处理 datetime / UUID 等非标准 JSON 类型"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if hasattr(obj, "hex"):
        return str(obj)
    return str(obj)


# ============================================================
# 业务缓存 Key 构造
# ============================================================

def post_key(post_id: str) -> str:
    return f"cache:post:{post_id}"

def user_key(user_id: str) -> str:
    return f"cache:user:{user_id}"

def feed_key(tenant_id: str, feed_type: str = "all", page: int = 1) -> str:
    return f"cache:feed:{tenant_id}:{feed_type}:p{page}"

def stats_key(user_id: str) -> str:
    return f"cache:stats:{user_id}"

def search_key(tenant_id: str, query: str) -> str:
    # 简单 hash 避免 key 含特殊字符
    import hashlib
    qhash = hashlib.md5(query.encode()).hexdigest()[:12]
    return f"cache:search:{tenant_id}:{qhash}"


# ============================================================
# 缓存失效规则
# ============================================================

async def invalidate_post(post_id: str):
    """帖子变更 → 删帖子缓存 + 相关 Feed 缓存"""
    await cache_delete(post_key(post_id))

async def invalidate_user(user_id: str):
    """用户资料变更 → 删用户名片 + 统计缓存"""
    await cache_delete(user_key(user_id), stats_key(user_id))

async def invalidate_feed(tenant_id: str):
    """有新帖 → 删所有 Feed 首页缓存 (全站+关注+用户)"""
    await cache_delete_pattern(f"cache:feed:{tenant_id}:*")

async def invalidate_stats(user_id: str):
    """关注/粉丝数变更 → 删统计缓存"""
    await cache_delete(stats_key(user_id))
