"""
Redis 计数器 → DB 批量同步 (Celery 定时任务)

每 30 秒运行一次:
  1. 扫描 Redis 中所有非零计数器
  2. 批量 UPDATE social_posts (单条 SQL per counter type)
  3. 重置 Redis 计数器 (避免重复累加)
"""

import logging

from celery import shared_task
from sqlalchemy import text

from app.core.counters import like_counter, comment_counter, view_counter

logger = logging.getLogger("opc.tasks.sync_counters")


@shared_task(
    name="sync_counters_to_db",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
    soft_time_limit=25,
    time_limit=30,
)
def sync_counters_to_db(self):
    """批量同步 Redis 计数器到 PostgreSQL"""
    import asyncio

    try:
        asyncio.run(_do_sync())
    except Exception as e:
        logger.error(f"Counter sync failed: {e}")
        raise self.retry(exc=e)


async def _do_sync():
    from app.core.database import async_session_factory

    async with async_session_factory() as db:
        for counter, col_name in [
            (like_counter, "like_count"),
            (comment_counter, "comment_count"),
            (view_counter, "view_count"),
        ]:
            dirty = await counter.get_all_dirty()
            if not dirty:
                continue

            # 批量 UPDATE: 单条 SQL 更新所有变化的帖子
            for post_id, val in dirty.items():
                await db.execute(
                    text(
                        f"UPDATE social_posts SET {col_name} = :val "
                        f"WHERE id = CAST(:pid AS uuid) AND {col_name} != :val"
                    ),
                    {"val": val, "pid": post_id},
                )

            await db.commit()
            logger.info(f"Synced {col_name}: {len(dirty)} posts")

            # 重置 Redis 计数器
            for post_id in dirty:
                await counter.reset(post_id)
